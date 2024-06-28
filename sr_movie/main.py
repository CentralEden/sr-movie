import ffmpeg
import os
import shutil
import datetime
import subprocess
import sys
import json

from conf.config import Config

import glob

def run_ffmpeg_command(input_file, output_file, command_args):
    """ ffmpeg-python を使用してコマンドを実行する """
    stream = ffmpeg.input(input_file)
    stream = stream.output(output_file, **command_args)
    ffmpeg.run(stream)

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
        audio_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'audio']
        if audio_streams:
            return audio_streams[0]['codec_name']
    except ffmpeg.Error as e:
        print(f"エラーが発生しました: {e.stderr}")
    return None
def get_video_properties(video_path):
    probe = ffmpeg.probe(video_path)
    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    frame_rate = eval(video_stream['r_frame_rate'])
    vcodec = video_stream['codec_name']
    pix_fmt = video_stream['pix_fmt']
    duration_seconds = float(probe['format']['duration'])
    duration_hms = str(datetime.timedelta(seconds=int(duration_seconds)))
    return frame_rate, vcodec, pix_fmt, duration_hms

def main():


    # コマンドライン引数からテストフラグを取得
    check_flag = False
    create_ds_flag = False
    gen_low_scale_flag = False
    if len(sys.argv) > 1:
        check_flag = sys.argv[1].lower() == 'check'
        create_ds_flag = sys.argv[1].lower() == 'create_ds'
        gen_low_scale_flag = sys.argv[1].lower() == 'gen_low_scale'
    

    # config.jsonファイルのパス
    conf = Config()

    if check_flag:
        print("Start Check Mode")
        input_path = os.path.join(conf.common.input_base_path , conf.common.input_file)
        output_base_path = create_directory_for_process(conf.common.output_base_path)
        video_info = ffmpeg.probe(input_path)
        total_duration = float(video_info['format']['duration'])
        time_intervals = []
        for seconds in range(0, int(total_duration), conf.check.output_interval_sec):  # 秒数
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            time_intervals.append(f"{hours:02}:{minutes:02}:{seconds:02}")
        for upscale in conf.check.upscale_rates:
            print(f"Upscale rate: {upscale}")
            upscale_output_folder = f'{output_base_path}\\upscale_{upscale}\\'
            resize_output_folder = f'{output_base_path}\\resize_{upscale}\\'
            os.makedirs(upscale_output_folder, exist_ok=True)
            os.makedirs(resize_output_folder, exist_ok=True)
            # resize
            for i, time_interval in enumerate(time_intervals[1:]):
                resize_image_path = f'{resize_output_folder}frame_{i:08d}.png'
                ffmpeg.input(input_path, ss=time_interval).output(resize_image_path, vframes=1,vf=f'scale={conf.check.output_px_width / upscale}:-1', vcodec='png').run(capture_stderr=True)           
            # super resolution
            command = ['python', '.\\Real-ESRGAN\\inference_realesrgan.py', '-i', resize_output_folder, '-o', upscale_output_folder, '-n', 'realesr-general-x4v3', '-g', '0', '-s', f'{upscale}']
            subprocess.run(command, shell=True, check=True)
    elif create_ds_flag:
        print("Start Create Dataset Mode")
        output_folder = conf.create_dataset.output_image_path
        os.makedirs(output_folder, exist_ok=True) 

        for input_path in conf.create_dataset.input_video_path:
            file_name_without_extension = os.path.splitext(os.path.basename(input_path))[0]
            video_info = ffmpeg.probe(input_path)
            total_duration = float(video_info['format']['duration'])
            time_intervals = []
            for seconds in range(0, int(total_duration), conf.create_dataset.frame_extraction_interval):
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                time_intervals.append(f"{hours:02}:{minutes:02}:{seconds:02}")
           
            for i, time_interval in enumerate(time_intervals[1:]):
                out_image_path = f'{output_folder}{file_name_without_extension}_frame_{i:08d}.png'
                print(f"Output: {out_image_path}")
                ffmpeg.input(input_path, ss=time_interval).output(out_image_path, vframes=1, vcodec='png').run(quiet=True, overwrite_output=True)
    elif gen_low_scale_flag:
        print("Start Generate Low Scale Image Mode")
        input_image_path = conf.gen_low_scale.input_image_path
        output_image_path = conf.gen_low_scale.output_image_path
        os.makedirs(output_image_path, exist_ok=True)
        width_px = conf.gen_low_scale.width_px
        path_list = sorted(glob.glob(os.path.join(input_image_path, '*')))
        for path in path_list:
            print(f"Input: {path}")
            out_image_path = f'{output_image_path}{os.path.basename(path)}'
            ffmpeg.input(path).output(out_image_path, vf=f'scale={width_px}:-1', vcodec='png').run(quiet=True, overwrite_output=True)

    else:
        print("Start Upscale Mode")
        input_file = conf.common.input_file
        time_segments = conf.upscale.time_segments
        upscale_rate = conf.upscale.upscale_rate
        input_path = os.path.join(conf.common.input_base_path , conf.common.input_file)
        output_base_path = conf.common.output_base_path
        output_base_path = create_directory_for_process(output_base_path)
        file_name_without_extension = os.path.splitext(input_file)[0]
        remove_tmp_flag = conf.upscale.remove_tmp_flag

        for i, (start_time, end_time) in enumerate(time_segments):
            print(f"Start Segment {i+1}: ({start_time} to {end_time})")
            trimmed_video = f'{output_base_path}\\trim_{i}.mp4'
            subprocess.run(['ffmpeg', '-ss', start_time, '-to', end_time, '-i', input_path, '-c:v', 'h264_nvenc', trimmed_video])
            # subprocess.run(['ffmpeg', '-ss', start_time, '-to', end_time, '-i', input_path, '-c', 'copy', trimmed_video])
            image_output_folder = f'{output_base_path}\\resize_img_{i}\\'
            os.makedirs(image_output_folder)
            run_ffmpeg_command(trimmed_video, f'{image_output_folder}image_%08d.png', {'vf': f'scale={1280 / upscale_rate}:-1', 'vcodec': 'png'})

            print("Start Super Resolution:", datetime.datetime.now())
            upscale_output_folder = f'{output_base_path}\\upscale_img_{i}\\'
            os.makedirs(upscale_output_folder, exist_ok=True)
            command = ['python', '.\\Real-ESRGAN\\inference_realesrgan.py', '-i', image_output_folder, '-o', upscale_output_folder, '--model_path', 'C:\\Users\\batyo\\Documents\\repo\\sr-movie\\Real-ESRGAN\\experiments\\finetune_RealESRGANx4plus_400k_pairdata\\models\\net_g_315000.pth', '-g', '0', '-s', f'{upscale_rate}', '-dn', "0.1"]
            # command = ['python', '.\\Real-ESRGAN\\inference_realesrgan.py', '-i', image_output_folder, '-o', upscale_output_folder, '-n', 'realesr-general-x4v3', '-g', '0', '-s', f'{upscale_rate}', '-dn', "0.1"]
            subprocess.run(command, shell=True, check=True)
            print("End Super Resolution:", datetime.datetime.now())

            if remove_tmp_flag:
                shutil.rmtree(image_output_folder)
                print(f"Delete {image_output_folder}")

            enhanced_video = f'{output_base_path}\\enhanced_video_{i}.mp4'
            frame_rate, vcodec, pix_fmt, duration_hms = get_video_properties(trimmed_video)
            print(f"Frame Rate: {frame_rate}, Video Codec: {vcodec}, Pixel Format: {pix_fmt}, Duration: {duration_hms}")
            run_ffmpeg_command(f'{upscale_output_folder}image_%08d_out.png', enhanced_video, {'t': duration_hms ,'r': f'{frame_rate}', 'vcodec': vcodec, 'pix_fmt': f'{pix_fmt}'})
            
            if remove_tmp_flag:
                shutil.rmtree(upscale_output_folder)
                print(f"Delete {upscale_output_folder}")

            final_output = f'{output_base_path}\\{file_name_without_extension}_{i}.mp4'
            command = ['ffmpeg', '-i', enhanced_video, '-i', trimmed_video, '-c:v', 'h264_nvenc', '-map', '0:v', '-c:a', 'copy', '-map', '1:a', final_output]
            subprocess.run(command, shell=True, check=True)

            print(f"End Segment {i+1}")
        output_path = os.path.join(os.path.dirname(input_path), f'{file_name_without_extension}_upscaled.mp4')
        if len(time_segments) > 1:
            final_videos = [f'{output_base_path}\\{file_name_without_extension}_{i}.mp4' for i in range(len(time_segments))]
            concat_command = ['ffmpeg', '-safe', '0', '-f', 'concat', '-i']
            with open(f'{output_base_path}\\filelist.txt', 'w') as filelist:
                for video in final_videos:
                    filelist.write(f"file '{video}'\n")
            concat_command.append(f'{output_base_path}\\filelist.txt')
            concat_command.extend(['-c', 'copy', output_path])
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


