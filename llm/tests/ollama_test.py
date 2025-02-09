import requests
import time
import threading
import statistics

OLLAMA_URL = "http://localhost:11434/api/generate"  # Ollama API URL
MODEL_NAME = "llama3:70b"  # Adjust to match your model

# Number of concurrent threads (simulating multiple users)
NUM_THREADS = 4  
# Number of sequential requests per thread
REQUESTS_PER_THREAD = 10

# Storage for results
response_times = []
token_counts = []
error_count = 0
lock = threading.Lock()  # To safely update shared variables

def send_request(thread_id):
    """
    Sends multiple sequential requests to the Ollama server and records response statistics.
    """
    global error_count

    local_response_times = []
    local_token_counts = []

    for i in range(REQUESTS_PER_THREAD):
        prompt = f"Thread {thread_id}, request {i+1}: Generate a Verilog testbench for a simple ALU."

        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "options": {
                "temperature": 0.3,
                "top_p": 0.7,
                "max_tokens": 1024
            }
        }

        start_time = time.time()
        try:
            response = requests.post(OLLAMA_URL, json=payload)
            elapsed_time = time.time() - start_time

            response_json = response.json()
            if "response" in response_json:
                local_response_times.append(elapsed_time)
                local_token_counts.append(len(response_json["response"].split()))
            else:
                with lock:
                    error_count += 1
                print(f"[ERROR] Thread {thread_id}, request {i+1}: {response_json}")

        except Exception as e:
            with lock:
                error_count += 1
            print(f"[ERROR] Thread {thread_id}, request {i+1} failed: {e}")

    # Store results safely
    with lock:
        response_times.extend(local_response_times)
        token_counts.extend(local_token_counts)

def main():
    threads = []
    print(f"Starting performance test with {NUM_THREADS} threads and {REQUESTS_PER_THREAD} requests per thread.")

    start_time = time.time()

    for thread_id in range(NUM_THREADS):
        thread = threading.Thread(target=send_request, args=(thread_id,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    total_time = time.time() - start_time

    # Aggregate results
    if response_times:
        avg_response_time = statistics.mean(response_times)
        median_response_time = statistics.median(response_times)
        p95_response_time = statistics.quantiles(response_times, n=100)[94]  # Approximate 95th percentile
    else:
        avg_response_time = median_response_time = p95_response_time = None

    if token_counts:
        avg_tokens_per_response = statistics.mean(token_counts)
    else:
        avg_tokens_per_response = None

    print("\n=== Performance Test Results ===")
    print(f"Total requests sent: {NUM_THREADS * REQUESTS_PER_THREAD}")
    print(f"Total time taken: {total_time:.2f} seconds")
    print(f"Total errors: {error_count}")
    print(f"Average response time: {avg_response_time:.2f} seconds")
    print(f"Median response time: {median_response_time:.2f} seconds")
    print(f"95th percentile response time: {p95_response_time:.2f} seconds")
    print(f"Average tokens per response: {avg_tokens_per_response:.2f}")

if __name__ == "__main__":
    main()
