import jpype
import time
import jpype.imports
import stripe 
import dotenv
import os

from jpype.types import *
from jpype import JImplements, JOverride, JImplementationFor
from stripe import StripeClient
from dotenv import load_dotenv

load_dotenv()

SECRET_API_KEY = os.getenv('SECRET_API_KEY')
TERMINAL_LOCATION_ID = os.getenv('TERMINAL_LOCATION_ID')
CUSTOMER_ID = os.getenv('CUSTOMER_ID')


# This is for illustration only, 
# Terminal SDKs should call a backend service to retrieve a connection token.
client = StripeClient(SECRET_API_KEY)
jpype.startJVM(classpath=['target/samplejar.jar'])

from com.stripe.stripeterminal import *
from com.stripe.stripeterminal.external.callable import *
from com.stripe.stripeterminal.external.models import *
from com.stripe.stripeterminal.log import *
from java.io import *
from com.stripe.stripeterminal.appinfo import *

@JImplements(TerminalListener)
class CustomTerminalListener:
    @JOverride
    def onConnectionStatusChange(self, status):
        print(status)
        print("onConnectionStatusChange: ")
    
    @JOverride
    def onPaymentStatusChange(self, status):
        print("onConnectionStatusChange: ")

@JImplements(ConnectionTokenProvider)
class CustomConnectionTokenProviderImpl:
    @JOverride

    def fetchConnectionToken(self, callback):
        try:
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
        print("Installing Update")
    
    @JOverride
    # public void onReportReaderSoftwareUpdateProgress(float progress)
    def onReportReaderSoftwareUpdateProgress(self, progress):
        print("Update progress: ")

    # public void onFinishInstallingUpdate(@Nullable ReaderSoftwareUpdate update, @Nullable TerminalException e) {
    @JOverride
    def onFinishInstallingUpdate(self, update, e):
        print ("Finished update")

    @JOverride
    def onRequestReaderInput(self, options):
        print("Request reader input: ")
    
    @JOverride
    def onRequestReaderDisplayMessage(self, message):
        print("Request reader display: ") 

    @JOverride
    def onBatteryLevelUpdate(self, batteryLevel, batteryStatus, isCharging):
        print("Battery Update")
    
print('hello')

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
        print("Successful Discovery")

    @JOverride
    def onFailure(self, e):
        print("Failed Discovery")

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
        print("Successful Connection")

    @JOverride
    def onFailure(self, e):
        self.is_complete = True
        self.failed = True
        print("Failed Discovery")

@JImplements(SetupIntentCallback)
class SetupIntentCallback:
    def __init__(self):
        self.is_complete = False
        self.setup_intent = None
        self.failed = False
        self.failure_message = None

    @JOverride
    def onSuccess(self, setupIntent):
        print(setupIntent)
        self.is_complete=True
        self.setup_intent= setupIntent

    @JOverride
    def onFailure(self, e):
        self.failed = True
       # self.failure_message = e.errorMessage
        self.is_complete=True
        print (e)
        #print("failed -- " + e.errorMessage)

# Setup Terminal
custom_mobile_reader_listener = CustomMobileReaderListener()
custom_connection_token_provider = CustomConnectionTokenProviderImpl()
custom_terminal_listener = CustomTerminalListener()
custom_discovery_listener = CustomDiscoveryListener()

long_value = JLong(0)

simulator_configuration = SimulatorConfiguration(SimulateReaderUpdate.NONE, SimulatedCard(SimulatedCardType.VISA), long_value, False, SimulatedCollectInputsResult.SimulatedCollectInputsResultSucceeded())

def discoverReaders():
    config = DiscoveryConfiguration.UsbDiscoveryConfiguration(0, True)
    Terminal.getInstance().discoverReaders(config, custom_discovery_listener, DiscoverReadersCallback())

    while not custom_discovery_listener.reader_list:
        print ('waiting for readers')
        time.sleep(2) 

    connectReader()


def connectReader():
    config = ConnectionConfiguration.UsbConnectionConfiguration(TERMINAL_LOCATION_ID, False, custom_mobile_reader_listener)
    # Hard-coding simulated reader M2
    Terminal.getInstance().connectReader(custom_discovery_listener.reader_list[1], config, ConnectReadersCallback())

def createConfirmSetupIntent():
    # Creating a Customer on the client, again just for illustration, this would have been done on a server
    setup_intent = client.setup_intents.create(params={
        "payment_method_types":["card_present"],
        "customer":CUSTOMER_ID,
    })
    setup_intent_retrieve_callback = SetupIntentCallback()


    Terminal.getInstance().retrieveSetupIntent(setup_intent.client_secret, setup_intent_retrieve_callback)
    while not setup_intent_retrieve_callback.is_complete:
        print("waiting for retrieve to complete")
        time.sleep(2)

    setup_intent_collect_callback = SetupIntentCallback()
    setup_intent_confirm_callback = SetupIntentCallback()

    Terminal.getInstance().collectSetupIntentPaymentMethod(setup_intent_retrieve_callback.setup_intent, AllowRedisplay.ALWAYS, setup_intent_collect_callback)

    while not setup_intent_collect_callback.is_complete:
        print("waiting for collect to complete")
        time.sleep(2)

    if setup_intent_collect_callback.failed:
        print("SetupIntent Failed")
        return

    Terminal.getInstance().confirmSetupIntent(setup_intent_collect_callback.setup_intent, setup_intent_confirm_callback)
    while not setup_intent_confirm_callback.is_complete:
        print("waiting for confirm to complete")
        time.sleep(2)

    if setup_intent_confirm_callback.failed:
        print ("SetupIntent Failed")
        return
     
    print ("COMPLETE!")

# uncomment this to get more logging, but it may be hard to interact with the terminal
log_level = LogLevel.NONE

file = File("/Users/tmcquinn/stripe/jpype-terminal-clear/testApp")
app_info = ApplicationInformation("hi-payment-service", "0.0.0", file)

if not Terminal.isInitialized():
    Terminal.initTerminal(custom_connection_token_provider, custom_terminal_listener, app_info, log_level, None)
    Terminal.getInstance().setSimulatorConfiguration(simulator_configuration)

user_input = input("ℹ️ Start? Y/N\n")

print (user_input)

if user_input.lower() == "y" or user_input.lower() == "yes":
    discoverReaders()
    print("Discovered Readers and Connected to simulated M2")
else:
    print ("done")

user_input = input("ℹ️ Proceed? Y/N\n")
if user_input.lower() == "y" or user_input.lower() == "yes":
    createConfirmSetupIntent()
else:
    print ("done")
