from reliable_signal import ReliableSignal

# Fired when a payment process reaches a terminal state (succeeded or failed).
# Receivers get: payment_process_id (int)
payment_process_completed = ReliableSignal()
