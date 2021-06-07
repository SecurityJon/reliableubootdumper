#######################################################
#       Imports
#######################################################
import serial, time, os, argparse


#######################################################
#       Global Variables
#######################################################
serialPortToUse = '/dev/ttyUSB0'
baudRateToUse = 115200
flashLocationInDecimal = 0
flashSize = 4 
tempfilepath = '/tmp/dumptemp.txt'
finalfilepath = '/tmp/dump.txt'
numberofBytestoRead = 3072

#######################################################
#       Progress bar code - borrowed from https://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console
#######################################################
def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

#######################################################
#       Fixing the output file code
#       For some reason the output file contains blank lines, we need to remove them
#######################################################
def fixOutputFile():
    if os.path.exists(finalfilepath):
      os.remove(finalfilepath)
    with open(tempfilepath, "r") as tempFile:
        with open(finalfilepath, "w") as finalFile:
            for line in tempFile:
                #strip out blank lines
                if not line == '\n':
                    finalFile.write(line)

        finalFile.close()
    tempFile.close()
    os.remove(tempfilepath)        

#######################################################
#       Serial initialization
#######################################################
ser = serial.Serial(serialPortToUse)  # open serial port
ser.baudrate = baudRateToUse
ser.bytesize = serial.EIGHTBITS #number of bits per bytes
ser.parity = serial.PARITY_NONE #set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE #number of stop bits
ser.timeout = 1            #non-block read
ser.xonxoff = False     #disable software flow control
ser.rtscts = False     #disable hardware (RTS/CTS) flow control
ser.dsrdtr = False       #disable hardware (DSR/DTR) flow control
ser.writeTimeout = 2     #timeout for write


#######################################################
#       Delete temporary files
#######################################################
def deleteTemporaryFlashDumpFile():
    if os.path.exists(tempfilepath):
      os.remove(tempfilepath)

#######################################################
#       Main Code
#######################################################
#If the serial is good to go
if ser.isOpen():
    try:
        #######################################################
        #       Parse User Input
        #######################################################        
        # Create the argument parser
        my_parser = argparse.ArgumentParser(description='Get arguments')

        # Add the arguments
        my_parser.add_argument('Path', metavar='path', type=str,  help='Path to the Output file to write to')
        my_parser.add_argument('Flash', metavar='flash', type=int,  help='The amount of Flash memory to dump, in megabytes, for example, 4')
        my_parser.add_argument('TTY', metavar='tty', type=str,  help='The serial interface to use, for example, /dev/ttyUSB0')
        my_parser.add_argument('Baud', metavar='baudrate', type=int,  help='The baud rate of the serial interface, for example, 115200')                

        # Execute the parse_args() method
        args = my_parser.parse_args()

        #Populate variables from user input
        serialPortToUse = args.TTY
        baudRateToUse = args.Baud        
        flashSize = args.Flash
        finalfilepath = args.Path
        tempfilepath = finalfilepath + "_temp"
        
        ser.flushInput() #flush input buffer, discarding all its contents
        ser.flushOutput()#flush output buffer, aborting current output 
                 #and discard all that is in buffer
            
        #Delete any temporary files before we start
        deleteTemporaryFlashDumpFile()
        
        #Create a temporay file to hold our flash dump
        dump_file = open(tempfilepath,'a')

        #######################################################
        #       Get the user to disconnect all other consoles
        #######################################################
        print("#######################################################")
        print("\tReliable Uboot Flash Dumper")
        print("#######################################################")
        print("")
        print("This tool does not handle multiple connections to the serial port well.")
        print("Please stop anything from using the serial port and press enter when you have done so")
        input()

        #Grab the time we started
        start_time = time.time()

        #######################################################
        #       Get OS location in flash from environment details
        #######################################################
        ser.write("printenv \r\n".encode('utf-8'))
        time.sleep(0.5)  #give the serial port sometime to receive the data
        numOfLines = 0       
        while True:
            response = ser.readline()
            decodedResponse = (response.decode())
            numOfLines = 0

            if "bootm" in decodedResponse:
                #Grab the exact flash location out of the returned string
                splitDecodedResponse = decodedResponse.split()
                for i in splitDecodedResponse:
                    if "0x" in i:
                        # Convert the flash location back into decimal
                        flashLocationInDecimal = int(i, 0)

                break
            else:
                numOfLines = numOfLines + 1            
            
            if (numOfLines >= 5):
                break

        #######################################################
        #       Get OS data from flash
        #######################################################
        ser.flushInput() #flush input buffer, discarding all its contents
        print("Dumping " + str(flashSize) + "MB of Flash. This will take a while")
        #Convert the number of MB we want into number of bytes
        numberOfBytesToGet = flashSize * 1024 * 1024
        finalFlashLocation = numberOfBytesToGet + flashLocationInDecimal
        flashLocationToReadInDecimal = flashLocationInDecimal
        #Convert the byte we want to get into hex
        numberofBytestoReadInHex = hex(numberofBytestoRead)
        print("Starting Dumping Flash at " + hex(flashLocationToReadInDecimal))
        
        #Top loop
        while True:
            ser.flushInput() #flush input buffer, discarding all its contents
            #Convert Flash location into hex
            flashLocationToReadInHex = hex(flashLocationToReadInDecimal)
            #print(str((finalFlashLocation - flashLocationToReadInDecimal) / 1024) + " kilobytes left")
            
            #Get a set of bytes and compare them
            flashReadCorrect = False
            while (flashReadCorrect == False):
                flashDump1 = ""
                flashDump2 = ""

                #Read one
                ser.flushInput() #flush input buffer, discarding all its contents
                toWrite = ("md.b " + str(flashLocationToReadInHex) + " " + str(numberofBytestoReadInHex) + " \r\n")
                ser.write(toWrite.encode('utf-8'))
                time.sleep(0.1)  #give the serial port sometime to receive the data

                while True:
                    response = ser.readline()
                    decodedResponse = (response.decode())

                    if ":" in decodedResponse:
                        flashDump1 = flashDump1 + decodedResponse
                    elif "md.b" in decodedResponse:
                        ignore = "ignore"
                    else:
                        break                        

                #Read two
                ser.flushInput() #flush input buffer, discarding all its contents
                toWrite = ("md.b " + str(flashLocationToReadInHex) + " " + str(numberofBytestoReadInHex) + " \r\n")
                ser.write(toWrite.encode('utf-8'))
                time.sleep(0.1)  #give the serial port sometime to receive the data

                while True:
                    response = ser.readline()
                    decodedResponse = (response.decode())

                    if ":" in decodedResponse:
                        flashDump2 = flashDump2 + decodedResponse
                    elif "md.b" in decodedResponse:
                        ignore = "ignore"
                    else:
                        break

                #Check if the two reads are the same, if they're not, bin out and try again
                if (flashDump1 == flashDump2):
                    flashReadCorrect = True
                    #print(flashDump1)
                    dump_file.write(flashDump1)
                    #Progress bar - lots of hacks in here to get it to work
                    whereWeAreForProgressBar = flashLocationToReadInDecimal - flashLocationInDecimal
                    whereToGetToForProgressBar = finalFlashLocation - flashLocationInDecimal
                    #print(str(whereWeAreForProgressBar) + " " + str(whereToGetToForProgressBar))
                    printProgressBar(whereWeAreForProgressBar, whereToGetToForProgressBar, prefix = 'Progress:', suffix = 'Complete', length = 50, printEnd = "\r\n")
                    break
                else:
                    print("Corruption detected reading flash, fixing. Aren't you glad you're running this tool?")


            #Check if we've read past where we want to
            if (flashLocationToReadInDecimal >= finalFlashLocation):
                #Fix the output file
                fixOutputFile()
                #Print the time this took to complete
                print("Complete! Execution time: " + str((time.time() - start_time) // 60) + "mins")
                print("File written to " + finalfilepath + " now run uboot_mdb_to_image.py")
                #Delete the temporary file
                dump_file.close()
                deleteTemporaryFlashDumpFile()
                break
            else:
                #Increment flash location to read        
                flashLocationToReadInDecimal = flashLocationToReadInDecimal + numberofBytestoRead
            
        ser.close()
    except Exception as e1:
        print("Error: " + str(e1))
        dump_file.close()

else:
    print("Cannot open serial port - did you need to use sudo?")
    dump_file.close()
