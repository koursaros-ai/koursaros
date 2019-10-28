import json

from gnes.router.base import BaseRouter
from gnes.proto import gnes_pb2
from gnes.helper import batching
from gnes.service.base import BlockMessage


from transformers import *
import torch
import torch.nn
import numpy as np


class RerankRouter(BaseRouter):

    def __init__(self, model_name: str = None, data_dir: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_name = model_name
        self.data_dir = data_dir
        self.max_grad_norm = 1.0
        self.lr = 1e-3

    def post_init(self):
        model_config = AutoConfig.from_pretrained(self.model_name, cache_dir=self.data_dir)
        model_config.num_labels = 1 # set up for regression
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.device == "cpu": self.logger.error("RUNING ON CPU")
        self.rerank_model = AutoModelForSequenceClassification.from_pretrained(self.model_name,
                                                                               config=model_config,
                                                                               cache_dir=self.data_dir)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, cache_dir=self.data_dir)
        self.rerank_model.to(self.device)

        self.optimizer = AdamW(self.rerank_model.parameters(), lr=self.lr, correct_bias=False)
        self.scheduler = ConstantLRSchedule(self.optimizer)

    def get_key(self, x: 'gnes_pb2.Response.QueryResponse.ScoredResult') -> str:
        return x.doc.doc_id

    def set_key(self, x: 'gnes_pb2.Response.QueryResponse.ScoredResult', k: str) -> None:
        x.doc.doc_id = k

    # @batching
    def apply(self, msg: 'gnes_pb2.Message', *args, **kwargs):

        all_scored_results = [sr for sr in msg.response.search.topk_results]
        runtime = getattr(msg, msg.WhichOneof('body')).WhichOneof('body')

        if runtime == 'train':  # training samples are given
            inputs = []
            labels = []
            for doc in msg.request.train.docs:
                ex = json.loads(doc.raw_bytes)
                inputs.append(
                    self.tokenizer.encode_plus(ex['Query'], ex['Candidate'], add_special_tokens=True))
                labels.append(float(ex['Label']))

            labels = torch.tensor(labels, dtype=torch.float).to(self.device)

        elif runtime == 'search':
            if len(msg.request.search.query.chunks) > 0:
                query = msg.request.search.query.chunks[0].text
            else:
                self.logger.error(msg)
            inputs = [
                self.tokenizer.encode_plus(
                    msg.request.search.query.doc.raw_text,
                    sr.chunk.text,
                    add_special_tokens=True,
                ) for sr in all_scored_results]
            self.logger.error(msg.request.search.query.chunks[0].text)
            self.logger.error(inputs)
            labels = None

        else:
            raise BlockMessage

        if len(inputs) == 0:
            print("Warning: empty input set, ignoring.")
            return

        max_len = max(len(t['input_ids']) for t in inputs)
        input_ids = [t['input_ids'] + [0] * (max_len - len(t['input_ids'])) for t in inputs]
        token_type_ids = [t['token_type_ids'] + [0] * (max_len - len(t['token_type_ids'])) for t in inputs]
        attention_mask = [[1] * len(t['input_ids']) + [0] * (max_len - len(t['input_ids'])) for t in inputs]

        input_ids = torch.tensor(input_ids).to(self.device)
        token_type_ids = torch.tensor(token_type_ids).to(self.device)
        attention_mask = torch.tensor(attention_mask).to(self.device)

        if labels is not None:
            loss = self.rerank_model(input_ids, token_type_ids=token_type_ids,
                                     labels=labels, attention_mask=attention_mask)[0]
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.rerank_model.parameters(), self.max_grad_norm)
            self.optimizer.step()
            self.scheduler.step()
            self.rerank_model.zero_grad()
            msg.response.train.status = gnes_pb2.Response.Status.SUCCESS

        else:
            with torch.no_grad():
                logits = self.rerank_model(input_ids, token_type_ids=token_type_ids,
                                           attention_mask=attention_mask)[0]
                scores = np.squeeze(logits.detach().cpu().numpy())
                if len(logits) == 1:
                    scores = [scores]
            ranked_results = []
            for sr, score in zip(all_scored_results, scores):
                ranked_results.append((sr.doc, score))

            k = msg.response.search.top_k
            top_k = sorted(ranked_results, key=lambda x: x[1], reverse=True)[:k]

            msg.response.search.ClearField('topk_results')
            for doc, score in top_k:
                sr = msg.response.search.topk_results.add()
                sr.score.value = float(score)
                sr.doc.CopyFrom(doc)
