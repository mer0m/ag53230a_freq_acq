#!/usr/bin/env python
"""
Created on Mon Aug 19 15:52:23 2013
53230a_freq_acq.py
This program is made to communicate with the counter
Agilent 53230A.
@author: Serge Grop
"""

import sys
import argparse
import socket
import time
import os

DEVICE_IP = '192.168.0.74'
DEVICE_PORT = 5025 # Agilent have standardized on using port 5025 for SCPI
#socket services.
GATE_TIME = 1 # Gate time for one measurement
OFILENAME = '' #File header
IN_COUP = 'AC' # Input coupling
IN_IMP = '50' # Input impedance
IN_CH = '1' # Input channel

#==============================================================================
def parse():
    """ Specific parsing procedure for transfering data from 53230a
    counter.
    Return parsed arguments."""
    parser = argparse.ArgumentParser( \
        description='Acquire data from 53230a counter connected '\
        'through Ethernet.',
        epilog='Example: \'53230a_acq_freq -o toto -c DC -i 1M \' configure ' \
        '53230a_acq_freq with output file toto-"date".dat, input coupling DC '\
        'and input impedance 1 MOhms.')
    parser.add_argument('-o', action='store', dest='ofile', \
                        default=OFILENAME,\
                        help='Output data filename (default '+OFILENAME+')')
    parser.add_argument('-c', action='store', dest='input_coupling', \
                        default=IN_COUP,\
                        help='Input coupling AC or DC (default '+IN_COUP+')')
    parser.add_argument('-i', action='store', dest='input_impedance', \
                        default=IN_IMP,\
                        help='Input impedance 50 or 1M (default '+IN_IMP+')')
    parser.add_argument('-t', action='store', dest='gatetime', \
                        default=GATE_TIME,\
                        help='Gate time for one measurement'\
                        ' (default '+str(GATE_TIME)+' second)')
    parser.add_argument('-ip', action='store', dest='ip', \
                        default=DEVICE_IP, help='IP address of the counter'\
                        ' (default '+str(DEVICE_IP)+')')
    parser.add_argument('-p', action='store', dest='port', \
                        default=DEVICE_PORT, help='Port of the counter'\
                        ' (default '+str(DEVICE_PORT)+')')
    parser.add_argument('-ch', action='store', dest='input_channel', \
                        default=IN_CH,\
                        help='Input channel (default '+IN_CH+')')
    args = parser.parse_args()
    return args

#==============================================================================
def connect(ip,port):
    """Creation of a socket to establish the communication
    with 53230a counter"""
    try:
        print '53230a connection state at "%s" ?' % ip
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, \
        socket.IPPROTO_TCP)
        sock.settimeout(5) 		# Don't hang around forever
        sock.connect((ip, port)) # Start the connection
        print '  --> Connected'
        return sock
    except socket.error as ex: # Debugging
        if 'Connection refused' in ex:
            print 'Wrong PORT (Default PORT : 5025)\n', ex
            print '\n  --> Not connected'
        elif 'No route to host' in ex:
            print 'Wrong address (Default address : 169.254.2.30)\n', ex
            print '\n  --> Not connected'
        else:
            print ex+'\n'+'  --> Not connected'
        sys.exit()

#==============================================================================
def init_53230a(sock, coupling, impedance, gatetime, channel):
    """Initialization of the counter"""
    g_time = 'SENS:FREQ:GATE:TIME '+str(gatetime)+'\n' # Definition of
    #the string to initialize the gate time
    sock.send("*RST\n") #Main reset
    sock.send("DISP:DIG:MASK:AUTO OFF\n") # Disable display autodigits
    if impedance == '50':
        sock.send("INP"+channel+":IMP 50\n") # Input 1 impedance : 50 Ohms
    else:
        sock.send("INP"+channel+":IMP 1.0E6\n") # Input 1 impedance : 1 MOhms
    if coupling == 'AC':
        sock.send("INP"+channel+":COUP AC\n") # Input 1 coupling mode AC
    else:
        sock.send("INP"+channel+":COUP DC\n") # Input 1 coupling mode DC
    sock.send("SYST:TIM INF\n") # Timeout infiny to avoid problem if the gate
    #is too long
    sock.send("CONF:FREQ (@"+channel+")\n") # Signal on input 1
    sock.send("SAMP:COUN 1E6\n") # Number of samples : 1 million (max)
    # the number of samples in continous mode is limited
    # by the size of the memory
    sock.send("SENS:FREQ:MODE CONT\n") # Continuous mode (gap free) enable
    sock.send("SENS:FREQ:GATE:SOUR TIME\n") # The gate source is TIME
    sock.send(g_time) # Gate time : 1 second
    sock.send("TRIG:SOUR IMM\n") # Because of the continuous mode

#==============================================================================
def check_error(sock):
    """Used for debugging during the development of the program,
    not used anymore"""
    sock.send('SYST:ERR?\n')
    error = None
    try:
        error = sock.recv(128)
    except socket.timeout:
        error = ""
    print error

#==============================================================================
def read_buffer(sock):
    """Read the data returned by the counter 53230a until the '\n'"""
    ans = ''
    nb_data_list = []
    nb_data = ''
    while ans != '\n':
        ans = sock.recv(1)
        nb_data_list.append(ans) # Return the number of data
    list_size = len(nb_data_list)
    for j in range (0, list_size):
        nb_data = nb_data+nb_data_list[j]
    return(nb_data) # Return the number of data in the memory


#==============================================================================
def acqu_53230a(i, sock, data_file, gatetime):
    """Frequency acquisition and stockage in a file"""
    sock.send("INIT:IMM\n") # Start the acquisition immediatly
    print "Waiting for the first acquisition"
    while True:
        try:
            sock.send("DATA:POIN?\n") # Ask the number of data in the memory
            nb_data = read_buffer(sock) # Number of data available (string)
            #nb_data_int = int(nb_data) # Convert in integer
            #epoch time
            epoch = time.time()
            #MJD time
            mjd = epoch / 86400.0 + 40587
            if nb_data != '+0\n': # There is a minimum of one data to read
                try:
                    sock.send("DATA:REM? 1\n") # Put the data in the buffer and
                    # clear the memory
                    freq = sock.recv(24) # Read the buffer
                    freq = freq[:22] # Remove \n from the string
                    freq = freq.replace("+", "")
                    freq = freq.replace("E", "e")
                    freq = freq.replace("\t", "")
                    sample = "%f\t%f\t%s\n" % (epoch, mjd, freq)
                    data_file.write(sample) # Write in a file
                    print sample
                except Exception as ex:
                    print "Exception during counter data reading: " + str(ex)
            else:
                #print "Waiting for the next acquisition"
                #pass
                time.sleep(int(gatetime)*0.1) # Wait the time of the gate time
                #to avoid too much check of the memory
        except KeyboardInterrupt:
            break # To stop the loop in a clean way

#==============================================================================
def main():
    """Main program"""
    args = parse() # Parse command line
    ofile = args.ofile # Data output file
    ip = args.ip
    coup = args.input_coupling
    imp = args.input_impedance
    gate_time = args.gatetime
    port = args.port
    ch = args.input_channel
    i = 0 #Init the number of sample
    sock = connect(ip, port)
    filename = time.strftime("%Y%m%d-%H%M%S", \
    time.gmtime(time.time()))+'-AG53230A_cont.dat' # Define the name of the file :
    # "experiment"+"date and hour".dat
    data_file = open(filename, 'wr', 0) # Create the file in write and read
    # mode, the file is updated at each sample
    #data_file.write('#Number of the sample-frequency in Hz-'\
    #'date when the data is computed\n')
    init_53230a(sock, coup, imp, gate_time, ch)
    acqu_53230a(i, sock, data_file, gate_time)
    sock.close()
    print '\n  --> Disconnected'
    data_file.close()
    try:
        ans = raw_input('Would you like to keep this datafile'\
        '(y/n : default y)?\t')
        if ans == 'n':
            os.remove(filename)
            print '\n', filename, 'removed\n'
        else:
            print '\n', filename, 'saved\n'
    except Exception as ex:
        print 'Oups '+str(ex)
    print 'Program ending\n'

#==============================================================================
if __name__ == "__main__":
    main()
