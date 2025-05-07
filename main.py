from math import log
import jpype
import time
import jpype.imports
import stripe 
import dotenv
import os
import logging

from jpype.types import *
from jpype import JImplements, JOverride, JImplementationFor
from stripe import StripeClient
from dotenv import load_dotenv

load_dotenv()


class SetupIntentComplete(Exception):
    pass 

SECRET_API_KEY = os.getenv('SECRET_API_KEY')
TERMINAL_LOCATION_ID = os.getenv('TERMINAL_LOCATION_ID')
CUSTOMER_ID = os.getenv('CUSTOMER_ID')
APP_LOCATION = os.getenv('APP_LOCATION')
USE_SIMULATOR = os.getenv('USE_SIMULATOR')

logging.basicConfig(
    filename='app.log',  # Set the filename for the log file
    level=logging.DEBUG,  # Set the logging level
    format='%(asctime)s - %(levelname)s - %(message)s',  # Define the log message format
)

file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)  # Log only ERROR and CRITICAL messages to the file

# # Example of logging to a stream
stream_handler = logging.StreamHandler()  # Typically stdout or stderr
stream_handler.setLevel(logging.INFO)  # Log INFO, WARNING, ERROR, CRITICAL, but not DEBUG
logging.getLogger('stripe').setLevel(logging.WARNING)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
  # Set the logger to DEBUG level
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

if logger.hasHandlers():
    logger.handlers.clear()
    
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# This is for illustration only, 
# Terminal SDKs should call a backend service to retrieve a connection token.
client = StripeClient(SECRET_API_KEY)
jpype.startJVM(classpath=['target/samplejar.jar'])

from com.stripe.stripeterminal import *
from com.stripe.stripeterminal.external.callable import *
from com.stripe.stripeterminal.external.models import *
from com.stripe.stripeterminal.log import *
from java.io import *
from java.lang import *
from com.stripe.stripeterminal.appinfo import *

file_path = "java_log.log"
file_output_stream = FileOutputStream(file_path)
file_output_stream_err = FileOutputStream("java_log_err.log")   
print_stream = PrintStream(file_output_stream)
print_stream_err = PrintStream(file_output_stream_err)

System.setOut(print_stream)
System.setErr(print_stream_err)


@JImplements(TerminalListener)
class CustomTerminalListener:
    @JOverride
    def onConnectionStatusChange(self, status):
        logging.debug("onConnectionStatusChange: " + str(status))
    
    @JOverride
    def onPaymentStatusChange(self, status):
        logging.debug("onConnectionStatusChange: " + str(status))

@JImplements(ConnectionTokenProvider)
class CustomConnectionTokenProviderImpl:
    @JOverride

    def fetchConnectionToken(self, callback):
        try:
            logging.debug("Fetching new Connection Token");
            connection_token = client.terminal.connection_tokens.create()
            callback.onSuccess(connection_token.secret)
        except Exception as e:
            exception = ConnectionTokenException("Failed to fetch connection token", e)
            callback.onFailure(exception)

@JImplements(MobileReaderListener)
class CustomMobileReaderListener:
    @JOverride
    # public void onStartInstallingUpdate(@NotNull ReaderSoftwareUpdate update, @NotNull Cancelable cancelable)
    def onStartInstallingUpdate(self, update, cancellable):
        logging.debug("Installing Update")
    
    @JOverride
    # public void onReportReaderSoftwareUpdateProgress(float progress)
    def onReportReaderSoftwareUpdateProgress(self, progress):
        logging.debug("Update progress: " + str(progress))

    # public void onFinishInstallingUpdate(@Nullable ReaderSoftwareUpdate update, @Nullable TerminalException e) {
    @JOverride
    def onFinishInstallingUpdate(self, update, e):
        logging.debug("Finished update")

    @JOverride
    def onRequestReaderInput(self, options):
        logging.info("Request reader input: " + str(options))
    
    @JOverride
    def onRequestReaderDisplayMessage(self, message):
        logging.info("Request reader display: " + str(message)) 

    @JOverride
    def onBatteryLevelUpdate(self, batteryLevel, batteryStatus, isCharging):
        logging.debug("Battery Update")
    
@JImplements(DiscoveryListener)
class CustomDiscoveryListener:
    def __init__(self):
        self.reader_list = None

    @JOverride
    def onUpdateDiscoveredReaders(self, readers):
        self.reader_list = readers

@JImplements(Callback)
class DiscoverReadersCallback:
    @JOverride
    def onSuccess(self):
        logging.debug("Successful Discovery")

    @JOverride
    def onFailure(self, e):
        logging.debug("Failed Discovery")

@JImplements(ReaderCallback)
class ConnectReadersCallback:
    def __init__(self):
        self.reader = None
        self.is_complete = False
        self.failed = False

    @JOverride
    def onSuccess(self, reader):
        self.reader = reader
        self.is_complete = True
        logging.debug("Successful Connection")

    @JOverride
    def onFailure(self, e):
        self.is_complete = True
        self.failed = True
        logging.debug("Failed Discovery")

@JImplements(SetupIntentCallback)
class SetupIntentCallback:
    def __init__(self):
        self.is_complete = False
        self.setup_intent = None
        self.failed = False
        self.failure_message = None

    @JOverride
    def onSuccess(self, setupIntent):
        logging.debug(setupIntent)
        self.is_complete=True
        self.setup_intent= setupIntent
        raise SetupIntentComplete

    @JOverride
    def onFailure(self, e):
        self.failed = True
       # self.failure_message = e.errorMessage
        self.is_complete=True
        logging.debug (e)
        #logging.debug("failed -- " + e.errorMessage)

@JImplements(Callback)
class CancelCallback:
    def __init__(self):
        self.is_complete = False
        self.failed = False

    @JOverride
    def onSuccess(self):
        self.is_complete= True
        logging.debug("Successful Cancel")

    @JOverride
    def onFailure(self, e):
        self.is_complete = False
        self.failed = True

        logging.debug("Failed Cancel")


# Setup Terminal
custom_mobile_reader_listener = CustomMobileReaderListener()
custom_connection_token_provider = CustomConnectionTokenProviderImpl()
custom_terminal_listener = CustomTerminalListener()
custom_discovery_listener = CustomDiscoveryListener()

long_value = JLong(0)

simulator_configuration = SimulatorConfiguration(SimulateReaderUpdate.NONE, SimulatedCard(SimulatedCardType.VISA), long_value, False, SimulatedCollectInputsResult.SimulatedCollectInputsResultSucceeded())

def discoverReaders():
    config = DiscoveryConfiguration.UsbDiscoveryConfiguration(0, USE_SIMULATOR)
    Terminal.getInstance().discoverReaders(config, custom_discovery_listener, DiscoverReadersCallback())

    while not custom_discovery_listener.reader_list:
        logging.info('Waiting for readers to be discovered...')
        time.sleep(2) 

    connectReader()

def askToCancelBasedOnCallback(cancelable):
    try:
        user_input = input("ℹ️ Would you like to cancel? Y/N\n")
        if user_input.lower() == "y" or user_input.lower() == "yes":
            cancel_callback = CancelCallback()
            cancelable.cancel(cancel_callback)

            while not cancel_callback.is_complete:
                logging.info("Waiting for Cancel to complete")
                time.sleep(2)
            
            if cancel_callback.failed: 
                logging.error("Cancel failed")
        
            logging.info("Cancel successful")

        return
    except SetupIntentComplete:
        logging.info("SetupIntent Complete")
        return
    except:
        return
    


def connectReader():
    config = ConnectionConfiguration.UsbConnectionConfiguration(TERMINAL_LOCATION_ID, False, custom_mobile_reader_listener)
    if USE_SIMULATOR == "true":
        # Hard-coding simulated reader M2
        Terminal.getInstance().connectReader(custom_discovery_listener.reader_list[1], config, ConnectReadersCallback())
    else:
        # just getting first reader
        Terminal.getInstance().connectReader(custom_discovery_listener.reader_list[0], config, ConnectReadersCallback())


def createConfirmSetupIntent():
    # Creating a Customer on the client, again just for illustration, this would have been done on a server
    setup_intent = client.setup_intents.create(params={
        "payment_method_types":["card_present"],
        "customer":CUSTOMER_ID,
    })
    setup_intent_retrieve_callback = SetupIntentCallback()


    Terminal.getInstance().retrieveSetupIntent(setup_intent.client_secret, setup_intent_retrieve_callback)
    while not setup_intent_retrieve_callback.is_complete:
        logging.info("Waiting for SetupIntent to be retrieved...")
        time.sleep(2)

    setup_intent_collect_callback = SetupIntentCallback()
    setup_intent_confirm_callback = SetupIntentCallback()

    cancelable = Terminal.getInstance().collectSetupIntentPaymentMethod(setup_intent_retrieve_callback.setup_intent, AllowRedisplay.ALWAYS, setup_intent_collect_callback)

    #askToCancelBasedOnCallback(cancelable) 

    while not setup_intent_collect_callback.is_complete:
        logging.info("waiting for collect to complete")
        time.sleep(2)

    if setup_intent_collect_callback.failed:
        logging.error("SetupIntent Failed")
        return

    Terminal.getInstance().confirmSetupIntent(setup_intent_collect_callback.setup_intent, setup_intent_confirm_callback)
    while not setup_intent_confirm_callback.is_complete:
        logging.info("waiting for confirm to complete")
        time.sleep(2)

    if setup_intent_confirm_callback.failed:
        logging.error ("SetupIntent Failed")
        return
     
    logging.info ("COMPLETE!")

def promptSetupIntent(first):
    user_input = input("ℹ️ Would you like to create " + ("" if first else "another ") + "a SetupIntent? Y/N\n")
    if user_input.lower() == "y" or user_input.lower() == "yes":
        createConfirmSetupIntent()
        promptSetupIntent(False)
        return 
    else:
        logging.info ("done")
        return

# uncomment this to get more logging, but it may be hard to interact with the terminal
log_level = LogLevel.VERBOSE
file = File(APP_LOCATION)
app_info = ApplicationInformation("hi-payment-service", "0.0.0", file)

if not Terminal.isInitialized():
    Terminal.initTerminal(custom_connection_token_provider, custom_terminal_listener, app_info, log_level, None)
    Terminal.getInstance().setSimulatorConfiguration(simulator_configuration)

user_input = input("ℹ️ Start? Y/N\n")

logging.debug (user_input)

if user_input.lower() == "y" or user_input.lower() == "yes":
    discoverReaders()
    logging.info("Discovered Readers and Connected to simulated M2")
else:
    logging.debug ("done")

promptSetupIntent(True)


file_output_stream.close()
print_stream.close()
jpype.shutdownJVM()
