import os
import traceback

import torch
from safetensors.torch import load_file
from torch import Tensor

from modules.model.WuerstchenModel import WuerstchenModel
from modules.util.ModelNames import ModelNames, EmbeddingName


class WuerstchenEmbeddingLoader:
    def __init__(self):
        super(WuerstchenEmbeddingLoader, self).__init__()

    def __load_embedding(
            self,
            embedding_name: str,
    ) -> Tensor | None:
        if embedding_name == "":
            return None

        try:
            embedding_state = torch.load(embedding_name)

            prior_text_encoder_vector = embedding_state['clip_g']

            return prior_text_encoder_vector
        except:
            pass

        try:
            embedding_state = load_file(embedding_name)

            prior_text_encoder_vector = embedding_state['clip_g']

            return prior_text_encoder_vector
        except:
            pass

        raise Exception(f"could not load embedding: {embedding_name}")

    def __load_internal(
            self,
            directory: str,
            embedding_name: EmbeddingName,
    ) -> Tensor | None:
        if os.path.exists(os.path.join(directory, "meta.json")):
            safetensors_embedding_name = os.path.join(
                directory,
                "embeddings",
                f"{embedding_name.uuid}.safetensors",
            )

            if os.path.exists(safetensors_embedding_name):
                return self.__load_embedding(safetensors_embedding_name)
            else:
                return self.__load_embedding(embedding_name.model_name)
        else:
            raise Exception("not an internal model")

    def load_multiple(
            self,
            model: WuerstchenModel,
            model_names: ModelNames,
    ):
        model.additional_embedding_states = []

        for embedding_name in model_names.additional_embeddings:
            stacktraces = []

            try:
                model.additional_embedding_states.append(self.__load_internal(model_names.base_model, embedding_name))
                continue
            except:
                try:
                    model.additional_embedding_states.append(self.__load_embedding(embedding_name.model_name))
                    continue
                except:
                    stacktraces.append(traceback.format_exc())

                stacktraces.append(traceback.format_exc())

                for stacktrace in stacktraces:
                    print(stacktrace)
                raise Exception("could not load embedding: " + str(model_names.embedding))

    def load_single(
            self,
            model: WuerstchenModel,
            model_names: ModelNames,
    ):
        stacktraces = []

        embedding_name = model_names.embedding

        try:
            model.embedding_state = self.__load_internal(model_names.embedding.model_name, embedding_name)
            return
        except:
            stacktraces.append(traceback.format_exc())

            try:
                model.embedding_state = self.__load_embedding(embedding_name.model_name)
                return
            except:
                stacktraces.append(traceback.format_exc())

        for stacktrace in stacktraces:
            print(stacktrace)
        raise Exception("could not load embedding: " + str(model_names.embedding))
