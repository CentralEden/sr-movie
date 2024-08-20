import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import urllib.request
import ffmpeg
import ruamel.yaml
from ruamel.yaml.scalarfloat import ScalarFloat
from conf.config import Config


def run_ffmpeg_command(input_file, output_file, command_args):
    """ffmpeg-python を使用してコマンドを実行する"""
    stream = ffmpeg.input(input_file)
    stream = stream.output(output_file, **command_args)
    ffmpeg.run(stream)


def float_representer(dumper, data):
    # 浮動小数点数を通常の小数点表記で表現
    return dumper.represent_scalar('tag:yaml.org,2002:float', format(data, 'f'))


def convert_exponential_to_float(d):
    if isinstance(d, dict):
        for k, v in d.items():
            d[k] = convert_exponential_to_float(v)
    elif isinstance(d, list):
        for i in range(len(d)):
            d[i] = convert_exponential_to_float(d[i])
    if isinstance(d, float):
        d = ScalarFloat(d, prec=6)
    return d


def replace_yaml_keys(input_yaml_path, output_yaml_path, replacements):
    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.representer.add_representer(ScalarFloat, float_representer)
    with open(input_yaml_path, 'r', encoding='utf-8') as file:
        yaml_content = yaml.load(file)

    for keys, new_value in replacements.items():
        # ネストされたキーにアクセスして値を置換
        d = yaml_content
        for key in keys[:-1]:
            d = d[key]
        d[keys[-1]] = new_value

    yaml_content = convert_exponential_to_float(yaml_content)
    print(yaml_content)
    with open(output_yaml_path, 'w', encoding='utf-8') as file:
        yaml.dump(yaml_content, file)


def create_directory_for_process(base_path):
    """プロセスIDに基づいてディレクトリを作成し、そのパスを返す関数"""
    # プロセスIDを取得
    process_id = os.getpid()
    # ディレクトリ名をプロセス名に設定
    directory_name = f"{base_path}{process_id}"
    # ディレクトリが存在しない場合は作成
    if not os.path.exists(directory_name):
        os.makedirs(directory_name)
        print(f"ディレクトリ {directory_name} を作成しました。")
    else:
        print(f"ディレクトリ {directory_name} は既に存在します。")

    # ディレクトリのパスを返す
    return directory_name


def get_audio_codec(video_path):
    """指定されたビデオから音声コーデックを取得する関数"""
    try:
        probe = ffmpeg.probe(video_path)
        audio_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "audio"]
        if audio_streams:
            return audio_streams[0]["codec_name"]
    except ffmpeg.Error as e:
        print(f"エラーが発生しました: {e.stderr}")
    return None


def get_video_properties(video_path):
    probe = ffmpeg.probe(video_path)
    video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)
    frame_rate = eval(video_stream["r_frame_rate"])
    vcodec = video_stream["codec_name"]
    pix_fmt = video_stream["pix_fmt"]
    duration_seconds = float(probe["format"]["duration"])
    duration_hms = str(datetime.timedelta(seconds=int(duration_seconds)))
    return frame_rate, vcodec, pix_fmt, duration_hms


def main():

    # コマンドライン引数からテストフラグを取得
    check_flag = False
    frame_extract_flag = False
    gen_low_scale_flag = False
    create_ds_flag = False
    fine_tuning_flag = False
    if len(sys.argv) > 1:
        check_flag = sys.argv[1].lower() == "check"
        create_ds_flag = sys.argv[1].lower() == "create_ds"
        gen_low_scale_flag = sys.argv[1].lower() == "gen_low_scale"
        frame_extract_flag = sys.argv[1].lower() == "frame_extract"
        fine_tuning_flag = sys.argv[1].lower() == "fine_tuning"

    # config.jsonファイルのパス
    conf = Config()

    if check_flag:
        print("Start Check Mode")
        input_path = os.path.join(conf.common.input_base_path, conf.common.input_file)
        output_base_path = create_directory_for_process(conf.common.output_base_path)
        video_info = ffmpeg.probe(input_path)
        total_duration = float(video_info["format"]["duration"])
        time_intervals = []
        for seconds in range(0, int(total_duration), conf.check.output_interval_sec):  # 秒数
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            time_intervals.append(f"{hours:02}:{minutes:02}:{seconds:02}")
        for upscale in conf.check.upscale_rates:
            print(f"Upscale rate: {upscale}")
            upscale_output_folder = f"{output_base_path}\\upscale_{upscale}\\"
            resize_output_folder = f"{output_base_path}\\resize_{upscale}\\"
            os.makedirs(upscale_output_folder, exist_ok=True)
            os.makedirs(resize_output_folder, exist_ok=True)
            # resize
            for i, time_interval in enumerate(time_intervals[1:]):
                resize_image_path = f"{resize_output_folder}frame_{i:08d}.png"
                ffmpeg.input(input_path, ss=time_interval).output(
                    resize_image_path, vframes=1, vf=f"scale={conf.check.output_px_width / upscale}:-1", vcodec="png"
                ).run(capture_stderr=True)
            # super resolution
            command = [
                "python",
                ".\\Real-ESRGAN\\inference_realesrgan.py",
                "-i",
                resize_output_folder,
                "-o",
                upscale_output_folder,
                "-n",
                "realesr-general-x4v3",
                "-g",
                "0",
                "-s",
                f"{upscale}",
            ]
            subprocess.run(command, shell=True, check=True)
    elif frame_extract_flag:
        print("Start Frame Extract Mode")
        output_folder = conf.frame_extract.output_image_path
        os.makedirs(output_folder, exist_ok=True)

        for input_path in conf.frame_extract.input_video_path:
            file_name_without_extension = os.path.splitext(os.path.basename(input_path))[0]
            video_info = ffmpeg.probe(input_path)
            total_duration = float(video_info["format"]["duration"])
            time_intervals = []
            for seconds in range(0, int(total_duration), conf.frame_extract.frame_extraction_interval):
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                time_intervals.append(f"{hours:02}:{minutes:02}:{seconds:02}")

            for i, time_interval in enumerate(time_intervals[1:]):
                out_image_path = f"{output_folder}{file_name_without_extension}_frame_{i:08d}.png"
                print(f"Output: {out_image_path}")
                ffmpeg.input(input_path, ss=time_interval).output(out_image_path, vframes=1, vcodec="png").run(
                    quiet=True, overwrite_output=True
                )
    elif gen_low_scale_flag:
        print("Start Generate Low Scale Image Mode")
        input_image_path = conf.gen_low_scale.input_image_path
        output_image_path = conf.gen_low_scale.output_image_path
        os.makedirs(output_image_path, exist_ok=True)
        width_px = conf.gen_low_scale.width_px
        path_list = sorted(glob.glob(os.path.join(input_image_path, "*")))
        for i, path in enumerate(path_list):
            print(f"({i}/{len(path_list)}) Input: {path}")
            out_image_path = f"{output_image_path}{os.path.basename(path)}"
            ffmpeg.input(path).output(out_image_path, vf=f"scale={width_px}:-1", vcodec="png").run(
                quiet=True, overwrite_output=True
            )
    
    elif create_ds_flag:
        print("Start Create Dataset Mode")
        input_image_path = conf.create_dataset.input_image_path
        root_path = Path(input_image_path).parent
        multiscale_path = os.path.join(root_path, "multiscale")
        os.makedirs(multiscale_path, exist_ok=True)
        # multiscale
        command = [
                "python",
                ".\\Real-ESRGAN\\scripts\\generate_multiscale_DF2K.py",
                "--input",
                input_image_path,
                "--output",
                multiscale_path,
            ]
        subprocess.run(command, shell=True, check=True)

        # meta info
        command = [
                "python",
                ".\\Real-ESRGAN\\scripts\\generate_meta_info.py",
                "--input",
                input_image_path,
                multiscale_path,
                "--root",
                root_path,
                root_path,
                "--meta_info",
                os.path.join(root_path, "meta_info.txt"),
            ]
        subprocess.run(command, shell=True, check=True)

        print("End Create Dataset Mode")

    elif fine_tuning_flag:
        print("Start Fine Tuning Mode")
        input_path = conf.fine_tuning.input_path

        # create training directory
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        training_directory = os.path.join("training", f"training_{current_time}")
        os.makedirs(training_directory, exist_ok=True)
        print(f"Trainingディレクトリ {training_directory} を作成しました。")
        
        # download pretrained model
        pretrained_model_path = ".\\Real-ESRGAN\\experiments\\pretrained_models\\"
        os.makedirs(os.path.dirname(pretrained_model_path), exist_ok=True)
        url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
        pretrained_model_file = os.path.join(pretrained_model_path, "RealESRGAN_x4plus.pth")
        if not os.path.exists(pretrained_model_file):
            urllib.request.urlretrieve(url, pretrained_model_file)
            print(f"Downloaded {url} to {pretrained_model_file}")
        url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.3/RealESRGAN_x4plus_netD.pth"
        pretrained_D_model_file = os.path.join(pretrained_model_path, "RealESRGAN_x4plus_netD.pth")
        if not os.path.exists(pretrained_D_model_file):
            urllib.request.urlretrieve(url, pretrained_D_model_file)
            print(f"Downloaded {url} to {pretrained_D_model_file}")

        # create train config yaml
        input_yaml_path = '.\\Real-ESRGAN\\options\\finetune_realesrgan_x4plus.yml'  # 入力YAMLファイルのパス
        output_yaml_path = os.path.join(training_directory, 'finetune_realesrgan_x4plus.yml')  # 出力YAMLファイルのパス
        replacements = {
            ('datasets', 'train', 'name'): f'training_{current_time}',
            ('datasets', 'train', 'dataroot_gt'): input_path,
            ('datasets', 'train', 'meta_info'): os.path.join(input_path, 'meta_info.txt'),
            ('path', 'pretrain_network_g'): pretrained_model_file,
            ('path', 'pretrain_network_d'): pretrained_D_model_file,
        }
        replace_yaml_keys(input_yaml_path, output_yaml_path, replacements)

        # Start training
        command = [
            "python",
            ".\\Real-ESRGAN\\realesrgan\\train.py",
            "-opt",
            output_yaml_path,
            "--auto_resume",
        ]
        subprocess.run(command, shell=True, check=True)

        print("End Fine Tuning Mode")


    else:
        print("Start Upscale Mode")
        input_file = conf.common.input_file
        time_segments = conf.upscale.time_segments
        upscale_rate = conf.upscale.upscale_rate
        input_path = os.path.join(conf.common.input_base_path, conf.common.input_file)
        output_base_path = conf.common.output_base_path
        output_base_path = create_directory_for_process(output_base_path)
        file_name_without_extension = os.path.splitext(input_file)[0]
        remove_tmp_flag = conf.upscale.remove_tmp_flag

        for i, (start_time, end_time) in enumerate(time_segments):
            print(f"Start Segment {i+1}: ({start_time} to {end_time})")
            trimmed_video = f"{output_base_path}\\trim_{i}.mp4"
            subprocess.run(
                ["ffmpeg", "-ss", start_time, "-to", end_time, "-i", input_path, "-c:v", "h264_nvenc", trimmed_video]
            )
            # subprocess.run(['ffmpeg', '-ss', start_time, '-to', end_time, '-i', input_path, '-c', 'copy', trimmed_video])
            image_output_folder = f"{output_base_path}\\resize_img_{i}\\"
            os.makedirs(image_output_folder)
            run_ffmpeg_command(
                trimmed_video,
                f"{image_output_folder}image_%08d.png",
                {"vf": f"scale={1280 / upscale_rate}:-1", "vcodec": "png"},
            )

            print("Start Super Resolution:", datetime.datetime.now())
            upscale_output_folder = f"{output_base_path}\\upscale_img_{i}\\"
            os.makedirs(upscale_output_folder, exist_ok=True)
            # command = ['python', '.\\Real-ESRGAN\\inference_realesrgan.py', '-i', image_output_folder, '-o', upscale_output_folder, '--model_path', 'C:\\Users\\batyo\\Documents\\repo\\sr-movie\\Real-ESRGAN\\experiments\\finetune_RealESRGANx4plus_400k_pairdata\\models\\net_g_latest.pth', '-g', '0', '-s', f'{upscale_rate}', '-dn', "0.1"]
            command = [
                "python",
                ".\\Real-ESRGAN\\inference_realesrgan.py",
                "-i",
                image_output_folder,
                "-o",
                upscale_output_folder,
                "-n",
                "realesr-general-x4v3",
                "-g",
                "0",
                "-s",
                f"{upscale_rate}",
                "-dn",
                "0.1",
            ]
            subprocess.run(command, shell=True, check=True)
            print("End Super Resolution:", datetime.datetime.now())

            if remove_tmp_flag:
                shutil.rmtree(image_output_folder)
                print(f"Delete {image_output_folder}")

            enhanced_video = f"{output_base_path}\\enhanced_video_{i}.mp4"
            frame_rate, vcodec, pix_fmt, duration_hms = get_video_properties(trimmed_video)
            print(f"Frame Rate: {frame_rate}, Video Codec: {vcodec}, Pixel Format: {pix_fmt}, Duration: {duration_hms}")
            command = [
                "ffmpeg",
                "-r",
                f"{frame_rate}",
                "-i",
                f"{upscale_output_folder}image_%08d_out.png",
                "-c:v",
                "h264_nvenc",
                enhanced_video
            ]
            subprocess.run(command, shell=True, check=True)

            if remove_tmp_flag:
                shutil.rmtree(upscale_output_folder)
                print(f"Delete {upscale_output_folder}")

            final_output = f"{output_base_path}\\{file_name_without_extension}_{i}.mp4"
            command = [
                "ffmpeg",
                "-i",
                enhanced_video,
                "-i",
                trimmed_video,
                "-c:v",
                "h264_nvenc",
                "-map",
                "0:v",
                "-c:a",
                "copy",
                "-map",
                "1:a",
                final_output,
            ]
            subprocess.run(command, shell=True, check=True)

            print(f"End Segment {i+1}")
        output_path = os.path.join(os.path.dirname(input_path), f"{file_name_without_extension}_upscaled.mp4")
        if len(time_segments) > 1:
            final_videos = [
                f"{output_base_path}\\{file_name_without_extension}_{i}.mp4" for i in range(len(time_segments))
            ]
            concat_command = ["ffmpeg", "-safe", "0", "-f", "concat", "-i"]
            with open(f"{output_base_path}\\filelist.txt", "w") as filelist:
                for video in final_videos:
                    filelist.write(f"file '{video}'\n")
            concat_command.append(f"{output_base_path}\\filelist.txt")
            concat_command.extend(["-c", "copy", output_path])
            subprocess.run(concat_command, shell=True, check=True)
            print(f"Create Merged Video: {output_path}")
        else:
            shutil.move(final_output, output_path)
            print("No need to merge because there is only one segment")

        if remove_tmp_flag:
            shutil.rmtree(output_base_path)
            print(f"Delete {output_base_path}")

        print(f"output_base_path: {output_base_path}")


if __name__ == "__main__":
    main()
