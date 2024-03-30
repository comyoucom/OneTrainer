import copy
import os.path
from pathlib import Path

import torch
import yaml
from safetensors.torch import save_file

from modules.model.StableDiffusionXLModel import StableDiffusionXLModel
from modules.modelSaver.mixin.DtypeModelSaverMixin import DtypeModelSaverMixin
from modules.util.convert.convert_sdxl_diffusers_to_ckpt import convert_sdxl_diffusers_to_ckpt
from modules.util.enum.ModelFormat import ModelFormat
from modules.util.enum.ModelType import ModelType


class StableDiffusionXLModelSaver(
    DtypeModelSaverMixin,
):

    def __save_diffusers(
            self,
            model: StableDiffusionXLModel,
            destination: str,
            dtype: torch.dtype | None,
    ):
        # Copy the model to cpu by first moving the original model to cpu. This preserves some VRAM.
        pipeline = model.create_pipeline()
        original_device = pipeline.device
        pipeline.to("cpu")
        pipeline_copy = copy.deepcopy(pipeline)
        pipeline.to(original_device)

        pipeline_copy.to("cpu", dtype, silence_dtype_warnings=True)

        os.makedirs(Path(destination).absolute(), exist_ok=True)
        pipeline_copy.save_pretrained(destination)

        del pipeline_copy

    def __save_ckpt(
            self,
            model: StableDiffusionXLModel,
            destination: str,
            dtype: torch.dtype | None,
    ):
        state_dict = convert_sdxl_diffusers_to_ckpt(
            model.vae.state_dict(),
            model.unet.state_dict(),
            model.text_encoder_1.state_dict(),
            model.text_encoder_2.state_dict(),
            model.noise_scheduler
        )
        save_state_dict = self._convert_state_dict_dtype(state_dict, dtype)
        self._convert_state_dict_to_contiguous(save_state_dict)

        os.makedirs(Path(destination).parent.absolute(), exist_ok=True)
        torch.save(save_state_dict, destination)

        yaml_name = os.path.splitext(destination)[0] + '.yaml'
        with open(yaml_name, 'w', encoding='utf8') as f:
            yaml.dump(model.sd_config, f, default_flow_style=False, allow_unicode=True)

    def __save_safetensors(
            self,
            model: StableDiffusionXLModel,
            destination: str,
            dtype: torch.dtype | None,
    ):
        state_dict = convert_sdxl_diffusers_to_ckpt(
            model.vae.state_dict(),
            model.unet.state_dict(),
            model.text_encoder_1.state_dict(),
            model.text_encoder_2.state_dict(),
            model.noise_scheduler
        )
        save_state_dict = self._convert_state_dict_dtype(state_dict, dtype)
        self._convert_state_dict_to_contiguous(save_state_dict)

        os.makedirs(Path(destination).parent.absolute(), exist_ok=True)

        save_file(save_state_dict, destination, self._create_safetensors_header(model, save_state_dict))

        yaml_name = os.path.splitext(destination)[0] + '.yaml'
        with open(yaml_name, 'w', encoding='utf8') as f:
            yaml.dump(model.sd_config, f, default_flow_style=False, allow_unicode=True)

    def __save_internal(
            self,
            model: StableDiffusionXLModel,
            destination: str,
    ):
        self.__save_diffusers(model, destination, None)

    def save(
            self,
            model: StableDiffusionXLModel,
            output_model_format: ModelFormat,
            output_model_destination: str,
            dtype: torch.dtype | None,
    ):
        match output_model_format:
            case ModelFormat.DIFFUSERS:
                self.__save_diffusers(model, output_model_destination, dtype)
            case ModelFormat.CKPT:
                self.__save_ckpt(model, output_model_destination, dtype)
            case ModelFormat.SAFETENSORS:
                self.__save_safetensors(model, output_model_destination, dtype)
            case ModelFormat.INTERNAL:
                self.__save_internal(model, output_model_destination)
