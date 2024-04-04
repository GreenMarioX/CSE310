from socket import *
import os

# Creating a server socket
server_socket = socket(AF_INET, SOCK_STREAM)
server_port = 8888
server_socket.bind(('', server_port))
server_socket.listen(5)

# Cache Creation
cache_directory = 'web_cache'
if not os.path.exists(cache_directory):
    os.makedirs(cache_directory)

# parses the request and returns the host and path.
def parse_request(url):
    if url.startswith("http://"):
        url = url[7:]

    host_path_split = url.split("/", 1)
    hostn = host_path_split[0]
    if len(host_path_split) > 1:
        path = "/" + host_path_split[1]  
    else:
        path = "/"

    return hostn, path

# Function to generate a valid file name for caching
def get_cache_file_name(url):
    return os.path.join(cache_directory, url.replace('/', '_'))

while True:
    # Accepting the connection
    print('Serving')
    client_socket, addr = server_socket.accept()
    print('Got connection from:', addr)

    message = client_socket.recv(1024).decode('utf-8')
    print(message)

    # Parsing the request
    first_line = message.split('\n')[0]
    url = first_line.split()[1][1:]

    hostname, path = parse_request(url)
    cache_file = get_cache_file_name(hostname + path)

    print("Host:", hostname)
    print("Path:", path)

    connection_sock = None
    try:
        # Cache Checking
        if os.path.isfile(cache_file):
            print("Serving from cache")
            with open(cache_file, 'rb') as f: # if in cache then use it
                client_socket.send(f.read())
        else:
            # If not in cache then connect to the server and get the response
            connection_sock = socket(AF_INET, SOCK_STREAM)
            connection_sock.connect((gethostbyname(hostname), 80))
            request = f"GET {path} HTTP/1.0\r\nHost: {hostname}\r\n\r\n"
            connection_sock.send(request.encode())

            # Writing to cache
            with open(cache_file, 'wb') as to_cache:
                response = connection_sock.recv(4096)
                while len(response) > 0:
                    client_socket.send(response)
                    to_cache.write(response)
                    response = connection_sock.recv(4096)
    # Exception Handling
    except Exception as e:
        print("Exception:", e)
        client_socket.send(b"HTTP/1.0 404 Not Found\r\n")
        client_socket.send(b"Content-Type:text/html\r\n")
        client_socket.send(b"\r\n")
    finally:
        if connection_sock:
            connection_sock.close()
        client_socket.close()

# Closing the server socket
server_socket.close()
