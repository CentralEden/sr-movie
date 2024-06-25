import ffmpeg
import os
import shutil
import datetime
import subprocess
import sys
import json

import cv2
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
    test_flag = False
    create_ds_flag = False
    gen_low_scale_flag = False
    if len(sys.argv) > 1:
        test_flag = sys.argv[1].lower() == 'test'
        create_ds_flag = sys.argv[1].lower() == 'create_ds'
        gen_low_scale_flag = sys.argv[1].lower() == 'gen_low_scale'
    

    # config.jsonファイルのパス
    config_path = os.path.join(os.path.dirname(__file__), '.\config.json')
    # config.jsonファイルを読み込む
    with open(config_path, 'r', encoding='utf-8') as config_file:
        opt = json.load(config_file)

    if test_flag:
        print("Start Test Mode")
        input_path = os.path.join(opt['common']['input_base_path'] , opt['common']['input_file'])
        output_base_path = create_directory_for_process(opt['common']['output_base_path'])
        video_info = ffmpeg.probe(input_path)
        total_duration = float(video_info['format']['duration'])
        time_intervals = []
        for seconds in range(0, int(total_duration), opt['test']['output_interval_sec']):  # 秒数
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            time_intervals.append(f"{hours:02}:{minutes:02}:{seconds:02}")
        for upscale in opt['test']['upscale_rates']:
            print(f"Upscale rate: {upscale}")
            upscale_output_folder = f'{output_base_path}\\upscale_{upscale}\\'
            resize_output_folder = f'{output_base_path}\\resize_{upscale}\\'
            os.makedirs(upscale_output_folder, exist_ok=True)
            os.makedirs(resize_output_folder, exist_ok=True)
            # resize
            for i, time_interval in enumerate(time_intervals[1:]):
                resize_image_path = f'{resize_output_folder}frame_{i:08d}.png'
                ffmpeg.input(input_path, ss=time_interval).output(resize_image_path, vframes=1,vf=f'scale={opt["test"]["output_px_width"] / upscale}:-1', vcodec='png').run()           
            # super resolution
            command = ['python', '.\\Real-ESRGAN\\inference_realesrgan.py', '-i', resize_output_folder, '-o', upscale_output_folder, '-n', 'realesr-general-x4v3', '-g', '0', '-s', f'{upscale}']
            print("実行するコマンド:", ' '.join(command))
            subprocess.run(command, shell=True, check=True)
    elif create_ds_flag:
        mode_opt = opt['create_dataset']
        print("データセット作成モードでの処理を開始します。")
        output_folder = mode_opt['output_image_path']
        os.makedirs(output_folder, exist_ok=True) 

        for input_path in mode_opt['input_video_path']:
            file_name_without_extension = os.path.splitext(os.path.basename(input_path))[0]
            video_info = ffmpeg.probe(input_path)
            total_duration = float(video_info['format']['duration'])
            time_intervals = []
            for seconds in range(0, int(total_duration), mode_opt['frame_extraction_interval']):  # 秒数
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                time_intervals.append(f"{hours:02}:{minutes:02}:{seconds:02}")
           
            for i, time_interval in enumerate(time_intervals[1:]):
                out_image_path = f'{output_folder}{file_name_without_extension}_frame_{i:08d}.png'
                print(f"Output: {out_image_path}")
                ffmpeg.input(input_path, ss=time_interval).output(out_image_path, vframes=1, vcodec='png').run(quiet=True)
    elif gen_low_scale_flag:
        mode_opt = opt['gen_low_scale']
        input_image_path = mode_opt['input_image_path']
        output_image_path = mode_opt['output_image_path']
        os.makedirs(output_image_path, exist_ok=True)
        width_px = mode_opt['width_px']
        path_list = sorted(glob.glob(os.path.join(input_image_path, '*')))
        for path in path_list:
            print(f"Input: {path}")
            out_image_path = f'{output_image_path}{os.path.basename(path)}'
            ffmpeg.input(path).output(out_image_path, vf=f'scale={width_px}:-1', vcodec='png').run(quiet=True, overwrite_output=True)

    else:

        input_file = '385174.mp4'
        time_segments = [
            ('00:10:07', '00:36:16'),
            # ('01:59:26', '02:31:40'),
            # 他の時間セグメントをここに追加
        ]
        upscale_rate = 4
        input_path = f'D:\\tmp\\sr_movie\\{input_file}'
        output_path = f'.\\out.mp4'        
        base_path = 'D:\\tmp\\sr_movie\\'
        base_path = create_directory_for_process(base_path)

        # ファイル名を取得
        file_name_without_extension = os.path.splitext(input_file)[0]

        for i, (start_time, end_time) in enumerate(time_segments):
            print(f"処理開始: セグメント {i+1} ({start_time} から {end_time})")
            # 動画切り出し
            trimmed_video = f'{base_path}\\trim_{i}.mp4'
            # ssをインプットに入れる
            subprocess.run(['ffmpeg', '-ss', start_time, '-to', end_time, '-i', input_path, '-c:v', 'h264_nvenc', trimmed_video])
            # subprocess.run(['ffmpeg', '-ss', start_time, '-to', end_time, '-i', input_path, '-c', 'copy', trimmed_video])
            # 画像変換
            image_output_folder = f'{base_path}\\resize_img_{i}\\'
            os.makedirs(image_output_folder)
            run_ffmpeg_command(trimmed_video, f'{image_output_folder}image_%08d.png', {'vf': f'scale={1280 / upscale_rate}:-1', 'vcodec': 'png'})

            # 超解像処理
            print("超解像処理開始:", datetime.datetime.now())
            # 超解像処理後の画像を出力するフォルダ名を定義してフォルダ作成
            upscale_output_folder = f'{base_path}\\upscale_img_{i}\\'
            os.makedirs(upscale_output_folder, exist_ok=True)
            command = ['python', '.\\Real-ESRGAN\\inference_realesrgan.py', '-i', image_output_folder, '-o', upscale_output_folder, '--model_path', 'C:\\Users\\batyo\\Documents\\repo\\sr-movie\\Real-ESRGAN\\experiments\\finetune_RealESRGANx4plus_400k_pairdata\\models\\net_g_5000.pth', '-g', '0', '-s', f'{upscale_rate}', '-dn', "0.1"]
            # command = ['python', '.\\Real-ESRGAN\\inference_realesrgan.py', '-i', image_output_folder, '-o', upscale_output_folder, '-n', 'realesr-general-x4v3', '-g', '0', '-s', f'{upscale_rate}', '-dn', "0.1"]
            print("実行するコマンド:", ' '.join(command))
            subprocess.run(command, shell=True, check=True)
            print("超解像処理終了:", datetime.datetime.now())

            # image_output_folderのフォルダ削除
            shutil.rmtree(image_output_folder)
            print(f"{image_output_folder} を削除しました")

            # 動画に戻す
            enhanced_video = f'{base_path}\\enhanced_video_{i}.mp4'
            # 動画のプロパティを取得して表示
            frame_rate, vcodec, pix_fmt, duration_hms = get_video_properties(trimmed_video)
            print(f"フレームレート: {frame_rate}, ビデオコーデック: {vcodec}, ピクセルフォーマット: {pix_fmt}, 動画時間: {duration_hms}")
            run_ffmpeg_command(f'{upscale_output_folder}image_%08d_out.png', enhanced_video, {'t': duration_hms ,'r': f'{frame_rate}', 'vcodec': vcodec, 'pix_fmt': f'{pix_fmt}'})
            # upscale_output_folderのフォルダ削除
            # shutil.rmtree(upscale_output_folder)
            # print(f"{upscale_output_folder} を削除しました")

            # 音声と結合
            final_output = f'{base_path}\\{file_name_without_extension}_{i}.mp4'
            command = ['ffmpeg', '-i', enhanced_video, '-i', trimmed_video, '-c:v', 'h264_nvenc', '-map', '0:v', '-c:a', 'copy', '-map', '1:a', final_output]
            subprocess.run(command, shell=True, check=True)

            print(f"処理終了: セグメント {i+1}")
        output_path = os.path.join(os.path.dirname(input_path), f'{file_name_without_extension}_upscaled.mp4')
        if len(time_segments) > 1:
            # すべてのセグメントの動画を結合
            final_videos = [f'{base_path}\\{file_name_without_extension}_{i}.mp4' for i in range(len(time_segments))]
            concat_command = ['ffmpeg', '-safe', '0', '-f', 'concat', '-i']
            with open(f'{base_path}\\filelist.txt', 'w') as filelist:
                for video in final_videos:
                    filelist.write(f"file '{video}'\n")
            concat_command.append(f'{base_path}\\filelist.txt')
            concat_command.extend(['-c', 'copy', output_path])
            subprocess.run(concat_command, shell=True, check=True)
            print(f"全セグメントを結合した動画を作成しました: {output_path}")
        else:
            shutil.move(final_output, output_path)
            print("セグメントが1つのため、結合処理は実施しません")

        # shutil.rmtree(base_path)
        print(f"base_path: {base_path}")

if __name__ == "__main__":
    main()


