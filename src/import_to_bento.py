import bentoml
import mlflow

BENTO_MODEL_NAME = "whisper_bento"
MLFLOW_MODEL_NAME = "Whisper_PTBR"

mlflow.set_tracking_uri("http://localhost:5000")  # Set the tracking URI to your MLflow server

def import_model_to_bento():
    try:
        # Load the model from MLflow
        model_uri = f"models:/{MLFLOW_MODEL_NAME}/latest"
        # model = mlflow.pyfunc.load_model(model_uri)
        bentoml.mlflow.import_model(BENTO_MODEL_NAME, model_uri)
        print("Modelo importado para BentoML com sucesso")

    except Exception as e:
        print(f"Erro ao importar o modelo para BentoML: {e}")

if __name__ == "__main__":
    import_model_to_bento()