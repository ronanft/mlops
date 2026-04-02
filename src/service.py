import bentoml
from pathlib import Path

@bentoml.service(
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