from socket import *

#connection stuff
serverPort = 6789
serverIP = ''
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind((serverIP, serverPort))
serverSocket.listen(1)

print("The server is ready to receive! Listening on Port:", serverPort)

while True:
        # Wait for a connection
        print("Waiting for input")
        connectionSocket, addr = serverSocket.accept()

        try:
            # Receive the message
            request = connectionSocket.recv(1024).decode()
            print("Request:", request)

            # Parse the request
            fileName = request.split('\n')[0].split()[1]
            if fileName.startswith('/'):
                fileName = fileName[1:]
            print("fileName:", fileName)

            # Handle File
            try: #handle file, returns header + content
                file = open(fileName, 'rb')
                content = file.read()
                file.close()
                header = b"HTTP/1.1 200 OK\r\n\r\n"
                http_res = header + content
            except FileNotFoundError: #handle no file, returns HTML
                header = b"HTTP/1.1 404 Not Found\r\n\r\n"
                content = b"<html><body><h1>404 Not Found</h1></body></html>"
                http_res = header + content
            connectionSocket.send(http_res)
        finally:
            print("Closed Connection")
            connectionSocket.close()


