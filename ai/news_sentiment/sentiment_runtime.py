"""Load once, reuse for all polling cycles. No model downloads."""
import json
from pathlib import Path
from model_identity import model_version
from model_inputs import INPUT_FORMAT, MARKED_FORMAT, encode_rows
from news_quality import assess

class Predictor:
    def __init__(self, folder):
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        self.torch=torch
        folder=Path(folder)
        if not (folder/'evaluation.json').exists(): raise ValueError('Evaluated model required')
        self.tokenizer=AutoTokenizer.from_pretrained(folder,local_files_only=True)
        self.model=AutoModelForSequenceClassification.from_pretrained(folder,local_files_only=True,use_safetensors=True)
        self.labels=['negative','neutral','positive']
        if [self.model.config.id2label[i] for i in range(3)]!=self.labels: raise ValueError('Label mapping mismatch')
        self.input_format=getattr(self.model.config,'stockpilot_input_format',None)
        if self.input_format not in (INPUT_FORMAT,MARKED_FORMAT): raise ValueError('Unknown input contract')
        calibration=folder/'calibration.json'
        self.temperature=float(json.loads(calibration.read_text(encoding='utf-8'))['temperature']) if calibration.exists() else 1.
        if not .05<=self.temperature<=20: raise ValueError('Invalid temperature')
        self.device='cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device).eval()
        self.version=model_version(folder)

    def predict(self, rows):
        result=[]
        with self.torch.inference_mode():
            for start in range(0,len(rows),16):
                batch=rows[start:start+16]
                tokens=encode_rows(self.tokenizer,batch,input_format=self.input_format,padding=True,return_tensors='pt')
                tokens={k:v.to(self.device) for k,v in tokens.items()}
                values=self.torch.softmax(self.model(**tokens).logits/self.temperature,dim=-1).cpu().tolist()
                for row,probs in zip(batch,values):
                    prediction=dict(zip(self.labels,probs),label=self.labels[max(range(3),key=lambda i:probs[i])])
                    prediction['quality']=assess(row,prediction)
                    result.append(prediction)
        return result
