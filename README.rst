# SR-MOVIE

このプロジェクトは、ffmpegとReal-ESRGANを使用して動画の超解像処理を行うためのスクリプトです。

## 必要な環境

- Python 3.x
- ffmpeg
- Real-ESRGAN

## インストール

1. リポジトリをクローンします。

git submodule update --init
poetry install
poetry shell
cd Real-ESRGAN
python setup.py develop