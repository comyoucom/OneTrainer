import os
import traceback

from modules.model.FluxModel import FluxModel
from modules.modelLoader.mixin.HFModelLoaderMixin import HFModelLoaderMixin
from modules.util.enum.ModelType import ModelType
from modules.util.ModelNames import ModelNames
from modules.util.ModelWeightDtypes import ModelWeightDtypes

import torch

from diffusers import (
    AutoencoderKL,
    FlowMatchEulerDiscreteScheduler,
    FluxPipeline,
    FluxTransformer2DModel,
)
from transformers import CLIPTextModel, CLIPTokenizer, T5EncoderModel, T5Tokenizer


class FluxModelLoader(
    HFModelLoaderMixin,
):
    def __init__(self):
        super().__init__()

    def __load_internal(
            self,
            model: FluxModel,
            model_type: ModelType,
            weight_dtypes: ModelWeightDtypes,
            base_model_name: str,
            transformer_model_name: str,
            vae_model_name: str,
            include_text_encoder_1: bool,
            include_text_encoder_2: bool,
    ):
        if os.path.isfile(os.path.join(base_model_name, "meta.json")):
            self.__load_diffusers(
                model, model_type, weight_dtypes, base_model_name, transformer_model_name, vae_model_name,
                include_text_encoder_1, include_text_encoder_2,
            )
        else:
            raise Exception("not an internal model")

    def __load_diffusers(
            self,
            model: FluxModel,
            model_type: ModelType,
            weight_dtypes: ModelWeightDtypes,
            base_model_name: str,
            transformer_model_name: str,
            vae_model_name: str,
            include_text_encoder_1: bool,
            include_text_encoder_2: bool,
    ):
        if include_text_encoder_1:
            tokenizer_1 = CLIPTokenizer.from_pretrained(
                base_model_name,
                subfolder="tokenizer",
            )
        else:
            tokenizer_1 = None

        if include_text_encoder_2:
            tokenizer_2 = T5Tokenizer.from_pretrained(
                base_model_name,
                subfolder="tokenizer_2",
            )
        else:
            tokenizer_2 = None

        noise_scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(
            base_model_name,
            subfolder="scheduler",
        )

        if include_text_encoder_1:
            text_encoder_1 = self._load_transformers_sub_module(
                CLIPTextModel,
                weight_dtypes.text_encoder,
                weight_dtypes.train_dtype,
                base_model_name,
                "text_encoder",
            )
        else:
            text_encoder_1 = None

        if include_text_encoder_2:
            text_encoder_2 = self._load_transformers_sub_module(
                T5EncoderModel,
                weight_dtypes.text_encoder_2,
                weight_dtypes.fallback_train_dtype,
                base_model_name,
                "text_encoder_2",
            )
        else:
            text_encoder_2 = None

        if vae_model_name:
            vae = self._load_diffusers_sub_module(
                AutoencoderKL,
                weight_dtypes.vae,
                weight_dtypes.train_dtype,
                vae_model_name,
            )
        else:
            vae = self._load_diffusers_sub_module(
                AutoencoderKL,
                weight_dtypes.vae,
                weight_dtypes.train_dtype,
                base_model_name,
                "vae",
            )

        if transformer_model_name:
            transformer = FluxTransformer2DModel.from_single_file(
                transformer_model_name,
                #avoid loading the transformer in float32:
                torch_dtype = torch.bfloat16 if weight_dtypes.prior.torch_dtype() is None else weight_dtypes.prior.torch_dtype()
            )
            transformer = self._convert_diffusers_sub_module_to_dtype(
                transformer, weight_dtypes.prior, weight_dtypes.train_dtype
            )
        else:
            transformer = self._load_diffusers_sub_module(
                FluxTransformer2DModel,
                weight_dtypes.prior,
                weight_dtypes.train_dtype,
                base_model_name,
                "transformer",
            )

        model.model_type = model_type
        model.tokenizer_1 = tokenizer_1
        model.tokenizer_2 = tokenizer_2
        model.noise_scheduler = noise_scheduler
        model.text_encoder_1 = text_encoder_1
        model.text_encoder_2 = text_encoder_2
        model.vae = vae
        model.transformer = transformer

    def __load_ckpt(
            self,
            model: FluxModel,
            model_type: ModelType,
            weight_dtypes: ModelWeightDtypes,
            base_model_name: str,
            vae_model_name: str,
            include_text_encoder_1: bool,
            include_text_encoder_2: bool,
            include_text_encoder_3: bool,
    ):
        # TODO
        pass

    def __load_safetensors(
            self,
            model: FluxModel,
            model_type: ModelType,
            weight_dtypes: ModelWeightDtypes,
            base_model_name: str,
            transformer_model_name: str,
            vae_model_name: str,
            include_text_encoder_1: bool,
            include_text_encoder_2: bool,
    ):
        transformer = FluxTransformer2DModel.from_single_file(
            #always load transformer separately even though FluxPipeLine.from_single_file() could load it, to avoid loading in float32:
            transformer_model_name if transformer_model_name else base_model_name,
            torch_dtype = torch.bfloat16 if weight_dtypes.prior.torch_dtype() is None else weight_dtypes.prior.torch_dtype()
        )
        pipeline = FluxPipeline.from_single_file(
            pretrained_model_link_or_path=base_model_name,
            safety_checker=None,
            transformer=transformer,
        )

        if include_text_encoder_2:
            # replace T5TokenizerFast with T5Tokenizer, loaded from the same repository
            pipeline.tokenizer_2 = T5Tokenizer.from_pretrained(
                pretrained_model_name_or_path="black-forest-labs/FLUX.1-dev",
                subfolder="tokenizer_2",
            )

        if vae_model_name:
            vae = self._load_diffusers_sub_module(
                AutoencoderKL,
                weight_dtypes.vae,
                weight_dtypes.train_dtype,
                vae_model_name,
            )
        else:
            vae = self._convert_diffusers_sub_module_to_dtype(
                pipeline.vae, weight_dtypes.vae, weight_dtypes.train_dtype
            )

        if pipeline.text_encoder is not None and include_text_encoder_1:
            text_encoder_1 = self._convert_transformers_sub_module_to_dtype(
                pipeline.text_encoder, weight_dtypes.text_encoder, weight_dtypes.train_dtype
            )
            tokenizer_1 = pipeline.tokenizer
        else:
            text_encoder_1 = None
            tokenizer_1 = None
            print("text encoder 1 (clip l) not loaded, continuing without it")

        if pipeline.text_encoder_2 is not None and include_text_encoder_2:
            text_encoder_2 = self._convert_transformers_sub_module_to_dtype(
                pipeline.text_encoder_2, weight_dtypes.text_encoder_2, weight_dtypes.fallback_train_dtype
            )
            tokenizer_2 = pipeline.tokenizer_2
        else:
            text_encoder_2 = None
            tokenizer_2 = None
            print("text encoder 2 (t5) not loaded, continuing without it")

        transformer = self._convert_diffusers_sub_module_to_dtype(
            pipeline.transformer, weight_dtypes.prior, weight_dtypes.train_dtype
        )

        model.model_type = model_type
        model.tokenizer_1 = tokenizer_1
        model.tokenizer_2 = tokenizer_2
        model.noise_scheduler = pipeline.scheduler
        model.text_encoder_1 = text_encoder_1
        model.text_encoder_2 = text_encoder_2
        model.vae = vae
        model.transformer = transformer

    def load(
            self,
            model: FluxModel,
            model_type: ModelType,
            model_names: ModelNames,
            weight_dtypes: ModelWeightDtypes,
    ):
        stacktraces = []

        try:
            self.__load_internal(
                model, model_type, weight_dtypes, model_names.base_model, model_names.prior_model, model_names.vae_model,
                model_names.include_text_encoder, model_names.include_text_encoder_2,
            )
            return
        except Exception:
            stacktraces.append(traceback.format_exc())

        try:
            self.__load_diffusers(
                model, model_type, weight_dtypes, model_names.base_model, model_names.prior_model, model_names.vae_model,
                model_names.include_text_encoder, model_names.include_text_encoder_2,
            )
            return
        except Exception:
            stacktraces.append(traceback.format_exc())

        try:
            self.__load_safetensors(
                model, model_type, weight_dtypes, model_names.base_model, model_names.prior_model, model_names.vae_model,
                model_names.include_text_encoder, model_names.include_text_encoder_2,
            )
            return
        except Exception:
            stacktraces.append(traceback.format_exc())

        for stacktrace in stacktraces:
            print(stacktrace)
        raise Exception("could not load model: " + model_names.base_model)
