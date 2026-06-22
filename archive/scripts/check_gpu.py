import torch
print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    t = torch.tensor([1.0, 2.0, 3.0], device="cuda")
    print(f"GPU tensor test: {t} -- OK")
else:
    print("GPU: NOT AVAILABLE - PyTorch was installed without CUDA support")
