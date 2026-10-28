"""Standalone worker: no application imports, remote code or model downloads."""
import json
import os
from pathlib import Path
import sys
import threading
import time


def watch_parent():
    """Exit on owner death, including an abrupt Desktop backend termination."""
    parent = int(os.environ.get("RASPUTIN_TRAINING_OWNER_PID") or os.getppid())
    cancel_file = os.environ.get("RASPUTIN_TRAINING_CANCEL_FILE")
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.WaitForSingleObject.restype = ctypes.c_ulong
        handle = kernel.OpenProcess(0x00100000, False, parent)
        if not handle:
            os._exit(1)
        # The handle remains bound to the original process even if its PID is reused.
        while True:
            if kernel.WaitForSingleObject(handle, 500) in (0, 0xFFFFFFFF) or (cancel_file and Path(cancel_file).exists()):
                os._exit(1)
    else:
        while os.getppid() == parent and not (cancel_file and Path(cancel_file).exists()):
            time.sleep(1)
        os._exit(1)


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}), flush=True)


def run():
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    import torch
    if not torch.cuda.is_available():
        emit("error", message="Training requires a CUDA-capable GPU and a matching PyTorch runtime.")
        return 1
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainerCallback
    from trl import SFTConfig, SFTTrainer

    class Progress(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            emit("progress", step=state.global_step, loss=(logs or {}).get("loss"))

    tokenizer = AutoTokenizer.from_pretrained(config["model_path"], local_files_only=True, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(config["model_path"], local_files_only=True,
                                                trust_remote_code=False, use_safetensors=True,
                                                torch_dtype=torch.float16)
    dataset = load_dataset("json", data_files=config["dataset_path"], split="train")
    args = SFTConfig(output_dir=config["output_dir"], max_steps=config["max_steps"],
                     learning_rate=config["learning_rate"], per_device_train_batch_size=1,
                     gradient_accumulation_steps=4, max_length=config["max_length"],
                     fp16=True, logging_steps=1, save_strategy="no", report_to="none",
                     dataset_text_field="text", dataloader_num_workers=0)
    trainer = SFTTrainer(model=model, processing_class=tokenizer, train_dataset=dataset, args=args,
                         peft_config=LoraConfig(r=config["rank"], lora_alpha=config["rank"] * 2,
                                                target_modules="all-linear", task_type="CAUSAL_LM"),
                         callbacks=[Progress()])
    trainer.train()
    trainer.save_model(config["output_dir"])
    tokenizer.save_pretrained(config["output_dir"])
    emit("complete")
    return 0


if __name__ == "__main__":
    threading.Thread(target=watch_parent, daemon=True).start()
    try:
        sys.exit(run())
    except Exception as exc:
        # Third-party exceptions can contain dataset text, tokens and private paths.
        emit("error", message=f"Training failed ({type(exc).__name__}). Check model compatibility and available GPU memory.")
        sys.exit(1)
