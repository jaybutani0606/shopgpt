from django.test import TestCase
from django.contrib.auth import get_user_model
import socket

class NetworkBlockerError(RuntimeError):
    pass

class BaseTestCase(TestCase):
    _original_socket = None
    _original_getaddrinfo = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Save original socket constructor and getaddrinfo
        cls._original_socket = socket.socket
        cls._original_getaddrinfo = socket.getaddrinfo
        
        # Override socket constructor and getaddrinfo to raise error on connection attempt
        def mock_socket(*args, **kwargs):
            raise NetworkBlockerError("Real network connection blocked in tests.")
            
        def mock_getaddrinfo(*args, **kwargs):
            raise NetworkBlockerError("DNS lookup blocked in tests.")
        
        socket.socket = mock_socket
        socket.getaddrinfo = mock_getaddrinfo

    @classmethod
    def tearDownClass(cls):
        # Restore original socket constructor and getaddrinfo
        if cls._original_socket is not None:
            socket.socket = cls._original_socket
        if cls._original_getaddrinfo is not None:
            socket.getaddrinfo = cls._original_getaddrinfo
        super().tearDownClass()

    def make_user(self, username="testuser", password="password123", **kwargs):
        User = get_user_model()
        return User.objects.create_user(username=username, password=password, **kwargs)
