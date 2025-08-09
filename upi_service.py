def generate_upi_link(service: str, upi_id: str, amount: float, note: str = "") -> str:
    base_uri = f"upi://pay?pa={upi_id}&am={amount:.2f}&cu=INR"
    if note:
        base_uri += f"&tn={note}"
    return base_uri
