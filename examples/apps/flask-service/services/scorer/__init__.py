from koursaros import Service
from utils.bucket import batch_fn
from utils.buffer import download_and_unzip
from koursaros.utils.model import Roberta
import os

CHECKPOINT_FILE = 'checkpoint_best.pt'
NAME = 'scorer'
MODELS_DIR = f'./'  # where to score the model locally

MODEL = f'{NAME}-model.tar.gz'  # bucket storage
BATCH_SIZE = 8
BUCKET = 'poloma-models'
model_dir = MODELS_DIR + f'{NAME}-output/'
if not os.path.isfile(model_dir + CHECKPOINT_FILE):
    print('downloading model...')
    download_and_unzip(BUCKET, MODEL, MODELS_DIR, archive=True)

regression_model = Roberta(
    MODELS_DIR + f'{NAME}-output/',
    CHECKPOINT_FILE,
    force_gpu=False
)

service = Service(__file__)

@service.stub
def rank(claim_with_lines, publish):
    def score(lines):
        claims = [claim_with_lines.claim.text] * len(lines)
        return regression_model.classify(claims, lines)

    results = []
    for scores, inputs in batch_fn(BATCH_SIZE, score, claim_with_lines.lines):
        for score, line in zip(scores, inputs):
            results.append((score, line))
    results.sort(key=lambda x: x[0], reverse=True)
    publish(service.messages.ClaimWithLines(
        claim=claim_with_lines.claim,
        lines=[el[1] for el in results[:5]]
    ))


def main():
    threads = service.run()

    for t in threads:
        t.start()

    for t in threads:
        t.join()