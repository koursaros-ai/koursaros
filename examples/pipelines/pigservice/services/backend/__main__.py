from koursaros.pipelines import pigservice
from flask import Flask, request, jsonify
from queue import Queue
from threading import Thread
import uuid

pipeline = pigservice(__file__)
app = Flask(__name__)
sentences = dict()


@app.route('/')
def receive():
    text = request.args.get('q')
    if not text:
        return jsonify({
            "status": "failure",
            "msg": "Please provide a sentence"
        })
    global sentences

    sentence_id = str(uuid.uuid4())
    queue = Queue()
    sentences[sentence_id] = queue

    sentence = pipeline.services.backend.stubs.send.Sentence(id=sentence_id, text=text)
    send_sentence(sentence)
    return jsonify({
        "status": "success",
        "msg": queue.get()
        })


@pipeline.services.backend.stubs.send
def send_sentence(sentence):
    print('SENDING')
    import pdb; pdb.set_trace()
    pipeline.services.pig.stubs.piggify(sentence)
    print('SENT')


@pipeline.services.backend.stubs.receive
def receive(piggified):
    global sentences
    sentences[piggified.sentence.id].put(piggified.pig_latin)


if __name__ == "__main__":
    s = Thread(target=pipeline.services.backend.run)
    a = Thread(target=app.run)

    s.start()
    a.start()
    s.join()
    a.join()


