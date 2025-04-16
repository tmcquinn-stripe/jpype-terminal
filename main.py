import jpype
import time
import jpype.imports
import stripe 

from jpype.types import *
from jpype import JImplements, JOverride, JImplementationFor
from stripe import StripeClient

# This is for illustration only, 
# Terminal SDKs should call a backend service to retrieve a connection token.
client = StripeClient("{{SECRET API KEY}}")
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
    @JOverride
    def onSuccess(self, reader):
        print("Successful Connection")

    @JOverride
    def onFailure(self, e):
        print("Failed Discovery")

@JImplements(SetupIntentCallback)
class SetupIntentCallback:
    def __init__(self):
        self.is_complete = False
        self.setup_intent = None

    @JOverride
    def onSuccess(self, setupIntent):
        self.is_complete=True
        self.setup_intent= setupIntent

    @JOverride
    def onFailure(self, e):
        print("failed")

# Setup Terminal
custom_mobile_reader_listener = CustomMobileReaderListener()
custom_connection_token_provider = CustomConnectionTokenProviderImpl()
custom_terminal_listener = CustomTerminalListener()
custom_discovery_listener = CustomDiscoveryListener()

long_value = JLong(0)

simulator_configuration = SimulatorConfiguration(SimulateReaderUpdate.NONE, SimulatedCard(SimulatedCardType.CHARGE_DECLINED_EXPIRED_CARD), long_value, False, SimulatedCollectInputsResult.SimulatedCollectInputsResultSucceeded())

def discoverReaders():
    config = DiscoveryConfiguration.UsbDiscoveryConfiguration(0, True)
    Terminal.getInstance().discoverReaders(config, custom_discovery_listener, DiscoverReadersCallback())

def connectReader():
    config = ConnectionConfiguration.UsbConnectionConfiguration("{{TERMINAL_LOCATION}}", False, custom_mobile_reader_listener)
    Terminal.getInstance().connectReader(custom_discovery_listener.reader_list[1], config, ConnectReadersCallback())

def createConfirmSetupIntent():
    # Creating a Customer on the client, again just for illustration, this would have been done on a server
    setup_intent = client.setup_intents.create(params={
        "payment_method_types":["card_present"],
        "customer":"{{CUSTOMER_ID}}",
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

    
    Terminal.getInstance().confirmSetupIntent(setup_intent_collect_callback.setup_intent, setup_intent_confirm_callback)
    while not setup_intent_confirm_callback.is_complete:
        print("waiting for confirm to complete")
        time.sleep(2)

    print ("COMPLETE!")

log_level = LogLevel.VERBOSE

file = File("/Users/tmcquinn/stripe/jpype-terminal-clear/testApp")
app_info = ApplicationInformation("hi-payment-service", "0.0.0", file)

if not Terminal.isInitialized():
    Terminal.initTerminal(custom_connection_token_provider, custom_terminal_listener, app_info, log_level, None)
    Terminal.getInstance().setSimulatorConfiguration(simulator_configuration)

user_input = input("Choose action:\n 1. Discover Readers \n 2. Connect Reader\n 3. Create/ConfirmSetupIntent")

print (user_input)

if user_input == "1":
    discoverReaders()
    print("discover reader done)")
else:
    print ("done")

while not custom_discovery_listener.reader_list:
    print ('waiting for readers')
    time.sleep(2)


print(custom_discovery_listener.reader_list)
user_input = input("Choose reader")

if user_input == "1":
    connectReader()

user_input = input("proceed")
if user_input == "1":
    createConfirmSetupIntent()


