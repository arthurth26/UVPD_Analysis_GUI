import sys, os, time, importlib, traceback
import numpy as np
from Python.workflows import convert_wiff_to_mzml, extract_RawData
from Python.main import main
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QTextEdit, QFileDialog, QTextEdit, QMessageBox
from PyQt5.QtGui import QTextCursor
from PyQt5 import QtWidgets
from io import StringIO

# Define a class that overwrite the printing option from terminal to a window within the GUI
class TextRedirect(StringIO):
    # Constructor (__init__ method) for the custom stream class
    def __init__(self, textWritten=None, *args, **kwargs):
        # Call the constructor of the parent class (StringIO)
        super().__init__(*args, **kwargs)
        # Store a callback function for updating external components with the written text
        self.update_output = textWritten

    # Override the write method of the parent class (StringIO)
    def write(self, text):
        # Call the write method of the parent class to perform the default writing
        super().write(text)
        # Invoke the stored callback function to notify external components with the written text
        self.update_output(text)

# Define a GUI class that inherits properties from PyQT5 QWidget
class GUI(QWidget):
    def __init__(self):
        # Call the constructor of the parent class (QWidget)
        super().__init__()

        # Call the initUI method to initialize the user interface
        self.initUI()

    #Specifies the user interface (ie. what does the GUI look like)
    def initUI(self):
        
        # Directory
        self.directory_label = QLabel('Directory that contains .wiff files or the mzml directory:')
        self.directory_line_edit = QLineEdit()
        self.directory_line_edit.setPlaceholderText('Example: D:\SampleData\CV_21')
        self.directory_button = QPushButton('Select Directory')
        self.directory_button.clicked.connect(self.browse_directory)

        # Base Peak Range
        self.base_peak_label = QLabel('Base Peak Range (comma-separated):')
        self.base_peak_line_edit = QLineEdit()
        self.base_peak_line_edit.setPlaceholderText('Example: 202.5,203.5')

        # Fragment Ion Ranges
        self.fragment_ion_label = QLabel('Fragment Ion Ranges (enclosed by brackets, comma-separated):')
        self.fragment_ion_line_edit = QLineEdit()
        self.fragment_ion_line_edit.setPlaceholderText('e.g., (50.5,51.5),(102.5,103.5),(125.5,127.9)')

        # Extract mzML from .wiff Flag
        self.extract_mzml_checkbox = QCheckBox('Extract mzML files from .wiff?')

        # PowerNorm Flag
        self.power_norm_checkbox = QCheckBox('Normalize to Laser Power? (Requires power data file)')

        # PrintRawData Flag
        self.print_raw_data_checkbox = QCheckBox('Print Raw Data?')

        # Power Data File Name
        self.power_data_label = QLabel('Power Data .csv file (Directory and/or Filename):')
        self.power_data_line_edit = QLineEdit()
        self.power_data_line_edit.setPlaceholderText('Example: D:\SampleData\power_400_600_100us.csv')

        # Output Text
        self.output_label = QLabel('Output:')
        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)

        # Run Button
        self.run_button = QPushButton('Analyze spectra')
        self.run_button.clicked.connect(self.run)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.directory_label)
        layout.addWidget(self.directory_line_edit)
        layout.addWidget(self.directory_button)

        layout.addWidget(self.base_peak_label)
        layout.addWidget(self.base_peak_line_edit)

        layout.addWidget(self.fragment_ion_label)
        layout.addWidget(self.fragment_ion_line_edit)

        layout.addWidget(self.extract_mzml_checkbox)
        layout.addWidget(self.power_norm_checkbox)
        layout.addWidget(self.print_raw_data_checkbox)

        layout.addWidget(self.power_data_label)
        layout.addWidget(self.power_data_line_edit)

        layout.addWidget(self.output_label)
        layout.addWidget(self.output_text_edit)

        layout.addWidget(self.run_button)

        self.setLayout(layout)

        self.setGeometry(300, 300, 500, 500)
        self.setWindowTitle('UVPD Data Analysis GUI')
        self.show()

    #button to browse existing directories. Selecting a directory here via this interface will populate the directory field
    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, 'Select Directory')
        self.directory_line_edit.setText(directory)

    #Function to update text being printed to the GUI's output window
    def update_output(self, text):
        cursor = self.output_text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.output_text_edit.setTextCursor(cursor)
        self.output_text_edit.ensureCursorVisible()

    #Function that executes the code when the run button is clicked    
    def run(self):
        
        start_time = time.time()

        # Redirect print output to QTextEdit
        sys.stdout = TextRedirect(textWritten=self.update_output)

        #print date and time to keep track of output from multiple runs. 
        now = datetime.now().replace(microsecond=0)
        print(f'{now}\n-------------\n')
        QApplication.processEvents()  # Allow the GUI to update 

        ########################################
        '''Directory Input and error handling'''
        ########################################

        directory = self.directory_line_edit.text()

        if not os.path.isdir(directory):
            print('The directory specified does not exist. Please provide a valid file path.\n')
            QApplication.processEvents()  # Allow the GUI to update 
            return

        ########################################
        '''Base peak input and error handling'''
        ########################################
        try:
            base_peak_input = self.base_peak_line_edit.text().replace(' ','').strip() #strip any whitespace within, before, or after the input

            #check that base peak range is not empty
            if not base_peak_input:
                print('The field for the base peak range is empty! Please populate it with two comma separated values.\n')
                QApplication.processEvents()  # Allow the GUI to update 
                return

            #check that there is at least one comma in the base peak range
            if ',' not in base_peak_input:
                print('No commas were found in the base peak range input. This needs to be two, comma separated numbers!\n')
                return
            
            try: 
                base_peak_range = list(map(float, base_peak_input.split(','))) #if there is at least 1 comma in the function, this shouldn't fail unless there are non-numeric characters
            except ValueError:
                print('Base peak input contains non-numeric characters!\n') #will throw value error because you cant float, for example, a100
                QApplication.processEvents()  # Allow the GUI to update 
                return

            #check that base peak range contains only two comma separated values
            if len(base_peak_range) != 2:
                print(f'You have specified {len(base_peak_range)} comma separated values for the base peak range.\nThe input for the base peak range can only be exactly two numbers separated by a comma (upper and lower limit of the m/z that surrounds the parent ion peak).\n')
                QApplication.processEvents()  # Allow the GUI to update 
                return
                                   
        except Exception as e: #for any other case that I can't think of
            print(f'Error parsing the input for the base peak: {e}\nTraceback: {traceback.format_exc()}\n')
            QApplication.processEvents()  # Allow the GUI to update 
            return 

        ############################################
        '''Fragment peak input and error handling'''
        ############################################

        fragment_ion_input = self.fragment_ion_line_edit.text().replace(' ','').strip() #strip any whitespace within, before, or after the input

        #check that fragment peak range is not empty
        if not fragment_ion_input:
            print('The field for the fragment peak range is empty! Please populate it using the proper format.\n')
            QApplication.processEvents()  # Allow the GUI to update 
            return
        
        else:
            try:
                # Check if the input contains any commas
                if ',' not in fragment_ion_input:
                    print('No commas were found in the fragment peak range input. Please use the specified format!\n')
                    QApplication.processEvents()  # Allow the GUI to update 
                    return
                
                if '(' not in fragment_ion_input or ')' not in fragment_ion_input:
                    print('No brackets were found in the fragment peak range input. Please use the specified format!\n')
                    QApplication.processEvents()  # Allow the GUI to update 
                    return                
                
                # Check if the input is in the form (number,number),(number,number),...
                try: 
                    fragment_ion_ranges = [list(map(float, pair.strip('()').split(','))) for pair in fragment_ion_input.split('),(')]
                
                except ValueError as ve:
                    print(f'Error parsing fragment ion input: {ve}\nFragment peak input likely contains non-numeric characters\n') #will throw value error because you cant float, for example, a100
                    QApplication.processEvents()  # Allow the GUI to update 
                    return
                
            except Exception as e:
                print(f'Other error when parsing fragment ion input: {e}\nTraceback: {traceback.format_exc()}\n')
                QApplication.processEvents()  # Allow the GUI to update 
                return
                
            # Check if each bracket in the fragment ion input has exactly two numbers
            if any(len(pair) != 2 for pair in fragment_ion_ranges):
                print('The input for each fragment ion (ie. the contents within each bracket) can only be exactly two numbers separated by a comma (upper and lower limit of the m/z that surrounds the fragment ion peak).\n')
                return
        
        #######################################
        '''Define radio buttons (checkboxes)'''
        #######################################
        
        extract_mzml_from_wiff_flag = self.extract_mzml_checkbox.isChecked() #Checkbox for extracting .wiff files
        power_norm_flag = self.power_norm_checkbox.isChecked()               #Checkbox for normalizing photofragmentation efficiency to laser power
        print_raw_data_flag = self.print_raw_data_checkbox.isChecked()       #Checkbox for printing the mass spectra used to calculate photofragmentation efficiency 
        
        ############################################
        '''Fragment peak input and error handling'''
        ############################################        
        
        power_data_file_name = self.power_data_line_edit.text().strip() #remove any trailing whitespaces from the filename

        #function to check if entires in the .csv are numeric
        def is_numeric_list(row):
            try:
                # Try to convert each entry in the row to a float
                float_entries = [float(entry) for entry in row]
                return True
            except ValueError:
                return False
        
        # Check if the file exists
        if power_norm_flag:
            if not os.path.isfile(power_data_file_name):
                print('The power data file could not be found. Please eheck that you have specified the directory and file name (with its extension!) properly.')
                QApplication.processEvents()  # Allow the GUI to update 
                return
            
            else:
                # Check if the file has a .csv extension
                if not power_data_file_name.lower().endswith('.csv'):
                    print('The power data file specified is not a .csv. Please ensure it is a comma separated value file (.csv).\n')
                    QApplication.processEvents()  # Allow the GUI to update 
                    return
                
                else:
                    #Check that the .csv is the correct format before starting the calculation. 
                    try:
                        # Read the first row of the CSV to check the number of columns
                        with open(power_data_file_name, 'r') as file:
                            first_row = file.readline().strip().split(',')
                        
                            # Check if the .csv contains three columns
                            if len(first_row) != 3:
                                print(f'The power data file .csv contains {len(first_row)} columns! Each row must only contain three numeric values with the following format:\nWavelength(nm), Laser power, and the StDev of the laser power.')
                                QApplication.processEvents()  # Allow the GUI to update 
                                return
                            
                            # Read the remaining rows to check if all entries are numeric
                            else:
                                
                                for line in file:
                                    row = line.strip().split(',')
                                    if len(row) != 3 or not is_numeric_list(row):
                                        print(f'This line in the .csv file: {line}\ndoes not meet the required format. Each row must only contain three numeric values with the following format:\nWavelength(nm), Laser power, and the StDev of the laser power.')
                                        QApplication.processEvents()  # Allow the GUI to update 
                                        return
                    except Exception as e:
                        print(f'Error encounters when attempting to open {power_data_file_name}:\n {e}\nTraceback: {traceback.format_exc()}')
                        QApplication.processEvents()  # Allow the GUI to update 
                        return

        # If the power_norm flag is unchecked, overwrite the contents of that input with None (will also work if no file is given)
        else:
            power_data_file_name = None 

        ###################################
        '''Preparing for code deployment'''
        ###################################           

        start = time.time() #get the time to determine overall calculation time. 
        if self.extract_mzml_checkbox.isChecked() == False:
            mzml_directory = directory #If the user did not want to extra the mzml files from wiff
        else:
            mzml_directory = os.path.join(directory, 'mzml_directory')  #directory for mzml files to be written to / where they are stored
        
        # Convert contents of each wiff file into an mzml (if requested)
        if extract_mzml_from_wiff_flag:
            print('Starting extraction of .wiff files. You may see a command prompt interface show up.\n\n')
            QApplication.processEvents()  # Allow the GUI to update  
            # List .wiff Files in the Directory and 
            wiff_files = [f for f in os.listdir(directory) if f.endswith('.wiff')]

            if len(wiff_files) == 0:
                print(f'There are no .wiff files present in {directory} to extract! Please specify a directory that contains .wiff files if you wish to extract them.\n')
                QApplication.processEvents()  # Allow the GUI to update  
                return

            # Create a directory to write the extracted .mzml files to
            try:
                os.mkdir(mzml_directory) #make thte mzml directory

            except FileExistsError:
                print(f'The user has requested to extract .mzml files from .wiff files, but the directory already exists.\nTo prevent overwriting files / combining incorrect data, please either:\n1. Uncheck the Extract mzml from wiff option, or\n2. Delete the exisitng mzml directory, and re-run the code with the Extract mzml from wiff option checked.\n')
                QApplication.processEvents()  # Allow the GUI to update
                return
            
            except Exception as e:
                print(f'A permission error has been encountered when trying to make {mzml_directory}.\nError: {e}\nTraceback: {traceback.format_exc()}\n')

            for wiff_file in wiff_files:
                wiff_stime = time.time() #define a time when the .wiff extraction starts
                try:
                    convert_wiff_to_mzml(wiff_file, directory, mzml_directory, update_output=self.update_output)
                    elapsed_time = np.round((time.time() - wiff_stime),1)
                    print(f'The wiff file:\n{wiff_file}\nhas been successfully extracted in {elapsed_time}s.')
                    QApplication.processEvents()  # Allow the GUI to update
                
                except Exception as e:
                    print(f'There was a problem extracting {wiff_file}. Please see the error below:\n{e}\n') #I don't really know how this can break, so we're using a broad exception. Surprise me, users!
                    print(f'{e}\n')
                    QApplication.processEvents()  # Allow the GUI to update
                    return

        # Execute the main function, which computes photofragmentation efficiency and writes the data to a file
        main(mzml_directory, base_peak_range, fragment_ion_ranges, power_data_file_name, update_output=self.update_output)

        # Redirect print output to QTextEdit again because something in main.py is killing this functionality
        sys.stdout = TextRedirect(textWritten=self.update_output)

        # Prints mass spectra to a .csv if user requests raw data via the checkbox
        if print_raw_data_flag:
            print('User has requested generation of raw data. Exporting mass spectra now...\n\n')
            QApplication.processEvents()  # Allow the GUI to update

            rawdata_file_name = os.path.join(directory,'Raw_data.csv')
            
            #mechanism to prevent overwriting existing output files
            index = 0

            while os.path.exists(rawdata_file_name):
                index += 1
                rawdata_file_name = os.path.join(directory,f'Raw_data_{index}.csv')

            parent_mz = (np.round(np.average(base_peak_range), 2))  # get parent mass - needed for the upper end of mz window for interpolation
            extract_RawData(mzml_directory, parent_mz, rawdata_file_name, update_output=self.update_output)
            
        run_time = np.round((time.time() - start_time)/60,1)

        print(f'UVPD photofragmentation efficiency calculation has completed in {run_time} minutes.\n\n')
        QApplication.processEvents()  # Allow the GUI to update

        # Reset print output redirection
        sys.stdout = sys.__stdout__

        return
   
    def close_application(self): # Exit alert for the user
        choice_title = 'Exit Confirmation'
        choice_prompt = 'Are you sure you wish to exit?'
        choice = QtWidgets.QMessageBox.question(self, choice_title, choice_prompt, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if choice == QtWidgets.QMessageBox.Yes:
           
            #close application
            sys.exit()

    def closeEvent(self, event):
        event.ignore() # Do not let the application close without a prompt
        self.close_application()

#The bit that actually starts the GUI
if __name__ == '__main__': #always and forever. 
    
    #Check for required python libraries before the GUI initializes
    def check_and_install_packages(package_list):
        missing_packages = [] #empty list to append missing packages to (if found)

        for package in package_list:
            try:
                globals()[package] = importlib.import_module(package)
            except (ModuleNotFoundError, ImportError):
                missing_packages.append(package)

        return missing_packages

    required_packages = ['pyqt5', 'pyteomics', 'numpy', 'pandas'] #modules required for the UVPD script
    missing_packages = check_and_install_packages(required_packages) 

    if missing_packages:
        print(f"The following packages could not be found: {' '.join(missing_packages)}")
        answer = input("Would you like to install them (y/n)? ")

        if answer.lower() == 'y':
            try:
                os.system(f"pip install {' '.join(missing_packages)}")
           
            except Exception as e:
                print(f'An exception has occured when trying to install {" ".join(missing_packages)}: {e}.\nTraceback: {traceback.format_exc()}\nPlease try to install the following packages via the command prompt: {" ".join(missing_packages)}')

            print("Packages installed successfully.")
            sys.exit()

    #start the GUI
    app = QApplication(sys.argv)
    gui = GUI()
    sys.exit(app.exec_())
