"""
Base class for sending a specific type of KNX/IP Packet to a KNX/IP device and wait for the corresponding answer.

Will report if the corresponding answer was not received.
"""
import asyncio
from xknx.knxip import ErrorCode

class RequestResponse():
    """Class for ending a specific type of KNX/IP Packet to a KNX/IP and wait for the corresponding answer."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, xknx, udp_client, awaited_response_class, timeout_in_seconds=1):
        """Initialize RequstResponse class."""
        self.xknx = xknx
        self.udpclient = udp_client
        self.awaited_response_class = awaited_response_class
        self.response_received_or_timeout = asyncio.Event()
        self.success = False
        self.timeout_in_seconds = timeout_in_seconds
        self.timeout_callback = None
        self.timeout_handle = None

    def create_knxipframe(self):
        """Create KNX/IP Frame object to be sent to device."""
        raise NotImplementedError('create_knxipframe has to be implemented')

    @asyncio.coroutine
    def start(self):
        """Start. Sending and waiting for answer."""
        callb = self.udpclient.register_callback(
            self.response_rec_callback, [self.awaited_response_class.service_type])

        yield from self.send_request()
        yield from self.start_timeout()
        yield from self.response_received_or_timeout.wait()
        yield from self.stop_timeout()

        self.udpclient.unregister_callback(callb)


    @asyncio.coroutine
    def send_request(self):
        """Build knxipframe (within derived class) and send via UDP."""
        knxipframe = self.create_knxipframe()
        knxipframe.normalize()

        self.udpclient.send(knxipframe)


    def response_rec_callback(self, knxipframe, _):
        """Callback for receiving answer. Checks if answer is of correct type."""
        if not isinstance(knxipframe.body, self.awaited_response_class):
            self.xknx.logger.warning("Cant understand knxipframe")
            return

        self.response_received_or_timeout.set()

        if knxipframe.body.status_code == ErrorCode.E_NO_ERROR:
            self.success = True
            self.on_success_hook(knxipframe)
        else:
            self.on_error_hook(knxipframe)


    def on_success_hook(self, knxipframe):
        """Hook for having received a valid answer. May be overwritten in derived class."""
        pass


    def on_error_hook(self, knxipframe):
        """Hook for having received an invalid answer. May be overwritten in derived class."""
        # pylint: disable=no-self-use
        self.xknx.logger.warning("Error: reading rading group address from KNX bus failed: %s", knxipframe.body.status_code)


    def timeout(self):
        """Handle timeout."""
        self.response_received_or_timeout.set()


    @asyncio.coroutine
    def start_timeout(self):
        """Start timeout."""
        self.timeout_handle = self.xknx.loop.call_later(
            self.timeout_in_seconds, self.timeout)

    @asyncio.coroutine
    def stop_timeout(self):
        """Stop timeout."""
        self.timeout_handle.cancel()