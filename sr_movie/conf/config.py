from pydantic import BaseModel
from typing import List, Tuple

class CommonConfig(BaseModel):
    input_base_path: str = "D:\\tmp\\sr_movie\\"
    input_file: str = "385174.mp4"
    output_base_path: str = "D:\\tmp\\sr_movie\\"

class CheckConfig(BaseModel):
    output_interval_sec: int = 300
    upscale_rates: List[int] = [1, 2, 4]
    output_px_width: int = 1280

class CreateDatasetConfig(BaseModel):
    input_video_path: List[str] = ["Z:\\create\\4k\\[activehlj.com]@SONE201_[4K].mkv"]
    output_image_path: str = "D:\\sr-movie\\training\\datasets\\raw_30\\"
    frame_extraction_interval: int = 30

class GenLowScaleConfig(BaseModel):
    input_image_path: str = "D:\\sr-movie\\training\\datasets\\raw\\"
    output_image_path: str = "D:\\sr-movie\\training\\datasets\\low_scale\\"
    width_px: int = 480

class UpscaleConfig(BaseModel):
    input_file: str = "385174.mp4"
    time_segments: List[Tuple[str, str]] = [("00:10:07", "00:36:16")]
    upscale_rate: int = 4
    remove_tmp_flag: bool = False

class Config(BaseModel):
    common: CommonConfig = CommonConfig()
    check: CheckConfig = CheckConfig()
    create_dataset: CreateDatasetConfig = CreateDatasetConfig()
    gen_low_scale: GenLowScaleConfig = GenLowScaleConfig()
    upscale: UpscaleConfig = UpscaleConfig()

# 使用例
if __name__ == "__main__":
    config = Config()
    print(config.common.input_base_path)