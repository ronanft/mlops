import bentoml
from pathlib import Path


whisper_transcriber = bentoml.images.Image(
    base_image="nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04",
    lock_python_packages=True  # Locks package versions for reproducibility
).python_packages(
    "bentoml",
    "mlflow",
    "torch",
    "transformers",
    "torchvision", # Adicionado
    "astunparse",   # Adicionado
    "jaraco-text",  # Adicionado
    "jmespath",     # Adicionado
    "optree"        # Adicionado
).system_packages(
    "python3",
    "python3-pip",
    "python3-venv",
    "python3-dev",
    "git",
    "ca-certificates",
    "ffmpeg"
    )

@bentoml.service(
    image=whisper_transcriber,
    resources={"gpu": 1},
    traffic={"timeout": 800},
)
class WhisperTranscriber():
    # Declare the model as a class variable
    bento_model = bentoml.models.BentoModel("whisper_bento:latest")

    def __init__(self):
        self.model = bentoml.mlflow.load_model(self.bento_model)

    @bentoml.api
    def transcribe(self, audio_file: Path) -> dict:
        
        audio_bytes = audio_file.read_bytes()

        result = self.model.predict(audio_bytes)
        return {
            "transcricao": result["text"],
            "status": "successo"
        }