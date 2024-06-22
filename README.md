# SR-MOVIE

このプロジェクトは、ffmpeg と Real-ESRGAN を使用して動画の超解像処理を行うためのスクリプトです。

## 必要な環境

- Python 3.x
- ffmpeg
- Real-ESRGAN

## インストール

1. リポジトリをクローンします。

```
git submodule update --init
poetry install
poetry shell
cd Real-ESRGAN
python setup.py develop
```

## Fine Tuning

### Prepare Dataset

```
python .\main.py create_ds
python .\Real-ESRGAN\scripts\generate_multiscale_DF2K.py --input .\training\datasets\raw --output .\training\datasets\multiscale
python .\Real-ESRGAN\scripts\generate_meta_info_pairdata.py --input .\training\datasets\raw .\training\datasets\multiscale --meta_info .\training\datasets\meta_info\meta_info_sub_pair.txt

python .\Real-ESRGAN\scripts\extract_subimages.py --input .\training\datasets\raw --output .\training\datasets\sub --crop_size 400 --step 200
python .\Real-ESRGAN\scripts\generate_multiscale_DF2K.py --input .\training\datasets\sub --output .\training\datasets\multiscale_sub
python .\Real-ESRGAN\scripts\generate_meta_info_pairdata.py --input .\training\datasets\sub .\training\datasets\multiscale_sub --meta_info .\training\datasets\meta_info\meta_info_sub_pair.txt

python .\Real-ESRGAN\scripts\generate_meta_info.py --input .\training\datasets\multiscale_sub --root .\training\datasets --meta_info .\training\datasets\meta_info\meta_info_multiscale.txt

python .\Real-ESRGAN\scripts\generate_meta_info.py --input .\training\datasets\raw --root .\training\datasets --meta_info .\training\datasets\meta_info\meta_info.txt
```

### Train

```
# HR only
Invoke-WebRequest -Uri https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth -outfile .\Real-ESRGAN\experiments\pretrained_models\RealESRGAN_x4plus.pth
Invoke-WebRequest -Uri https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.3/RealESRGAN_x4plus_netD.pth -outfile .\Real-ESRGAN\experiments\pretrained_models\RealESRGAN_x4plus_netD.pth
cp .\Real-ESRGAN\options\finetune_realesrgan_x4plus.yml  .\training
cp .\Real-ESRGAN\options\finetune_realesrgan_x4plus_pairdata.yml  .\training
python .\Real-ESRGAN\realesrgan\train.py -opt .\training\finetune_realesrgan_x4plus.yml --debug

python .\Real-ESRGAN\realesrgan\train.py -opt .\training\finetune_realesrgan_x4plus.yml --auto_resume

# pair
python .\Real-ESRGAN\realesrgan\train.py -opt .\training\finetune_realesrgan_x4plus_pairdata.yml --auto_resume
```
