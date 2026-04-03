import mlflow
from transformers import pipeline
import torch
from typing import Any
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

class WhisperPyFunc(mlflow.pyfunc.PythonModel):  # type: ignore
    def load_context(self, context):
        model_id = "freds0/whisper-small-portuguese"
        has_cuda = torch.cuda.is_available()
        device = "cuda:0" if has_cuda else "cpu"
        torch_dtype = torch.float16 if has_cuda else torch.float32

        self.pipeline = pipeline(
            "automatic-speech-recognition",
            model=model_id,
            device=device,
            torch_dtype=torch_dtype
        )

    def predict(self, context, model_input):
        if isinstance(model_input, bytes):
            return self.pipeline(model_input)
        raise ValueError("Input deve ser bytes")

# Configurar MLflow
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI_LOCAL", "http://localhost:5000"))
mlflow.set_experiment("Transcricoes-PTBR-v3")

with mlflow.start_run():
    mlflow.pyfunc.log_model(
        "whisper_ptbr_bento",
        python_model=WhisperPyFunc(),
        registered_model_name="transcritor-PTBR-pyfunc"
    )
    print("Modelo PyFunc registrado!")
