# Скрипт обучения модели

import json
from dataclasses import dataclass
from typing import Dict, List
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    set_seed,
)

@dataclass
class Example:
    word: str
    parts: List[str]
    lang: str

# Загружаем
def load_jsonl(path: str) -> List[Example]:
    items: List[Example] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            items.append(Example(
                word=obj["input"]["word"],
                parts=obj["target"]["parts"],
                lang=obj["input"].get("lang", "en")
            ))
    return items

# Преобразуем
def to_hf_dataset(examples: List[Example]) -> Dataset:
    return Dataset.from_dict({
        "word": [e.word for e in examples],
        "target": [" + ".join(e.parts) for e in examples],
        "lang": [e.lang for e in examples],
    })

# Гиперпараметры
TRAINING_KWARGS = dict(
    output_dir="models/decomposer_multilingual",
    num_train_epochs=10,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    gradient_accumulation_steps=2,
    learning_rate=3e-4,
    logging_steps=50,
    save_strategy="epoch",
    save_total_limit=2,
    predict_with_generate=True,
    eval_strategy="epoch",
    generation_max_length=64,
    report_to=[],
    dataloader_num_workers=0,
    use_cpu=False,
)

def main():
    set_seed(42)
    
    # Загрузка
    examples = load_jsonl("data/final_dataset.jsonl")

    # Статистика по языкам
    from collections import Counter
    lang_counts = Counter(ex.lang for ex in examples)

    # Подготовка данных
    ds = to_hf_dataset(examples).shuffle(seed=42)
    split = ds.train_test_split(test_size=0.1, seed=42)
    train_ds, eval_ds = split["train"], split["test"]

    # Модель
    tokenizer = AutoTokenizer.from_pretrained("google/byt5-small")
    model = AutoModelForSeq2SeqLM.from_pretrained("google/byt5-small")
    
    # Предобработка
    def preprocess(batch: Dict[str, List[str]]):
        inputs = [f"decompose {lang}: {word}" for word, lang in zip(batch["word"], batch["lang"])]
        targets = batch["target"]
        
        model_inputs = tokenizer(inputs, max_length=64, truncation=True, padding="max_length")
        labels = tokenizer(targets, max_length=64, truncation=True, padding="max_length")["input_ids"]
        
        labels = [[tok if tok != tokenizer.pad_token_id else -100 for tok in seq] for seq in labels]
        model_inputs["labels"] = labels
        return model_inputs
    
    train_tok = train_ds.map(preprocess, batched=True, remove_columns=train_ds.column_names)
    eval_tok = eval_ds.map(preprocess, batched=True, remove_columns=eval_ds.column_names)
    
    # Обучение
    training_args = Seq2SeqTrainingArguments(**TRAINING_KWARGS)
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_tok,
        eval_dataset=eval_tok,
        tokenizer=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer, model=model),
    )
    
    trainer.train()
    trainer.save_model()

if __name__ == "__main__":
    main()