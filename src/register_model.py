import mlflow
import torch
from transformers import pipeline
from mlflow import transformers as mltransformers

model_name = "Whisper_PTBR"
model_id = "freds0/whisper-small-portuguese"
device = "cuda" if torch.cuda.is_available() else "cpu"

mlflow.set_tracking_uri("http://localhost:5000")  # Set the tracking URI to your MLflow server
mlflow.set_experiment("Whisper_PTBR_v1")  # Set the experiment name

def register_model():
    # Start an MLflow run
    with mlflow.start_run():

        pipe = pipeline(
            "automatic-speech-recognition",
            model=model_id,
            chunk_length_s=30,
            device=device,
        )

        model_info = mltransformers.log_model(
            transformers_model=pipe,
            registered_model_name=model_name,
            artifact_path="whisper_model"
        )

        # Log the hyperparameters
        mlflow.log_params({"model_name": model_name, "model_base": model_id})
        print(f"Modelo registrado com sucesso")

if __name__ == "__main__":
    register_model()