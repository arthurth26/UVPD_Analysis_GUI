import os, re, time, sys, traceback
import numpy as np
from Python.workflows import integrate_spectra, PE_calc, PE_calc_noNorm
from PyQt5.QtWidgets import QApplication
from io import StringIO

class TextRedirect(StringIO):
    def __init__(self, textWritten=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_output = textWritten

    def write(self, text):
        super().write(text)
        self.update_output(text)

# Main function (aka where the magic happens)
def main(directory, base_peak_range, fragment_ion_ranges, power_data_file_name, update_output=None):
    
    # Redirect print outputs to the GUI output window
    sys.stdout = TextRedirect(textWritten=update_output)

    #print statements are now called with update_output in order for the text to be directed to the GUI window
    update_output('\nStarting interpolation and integration of mass spectra and calculation of photogragmentaion efficiency...\n\n')
    QApplication.processEvents()  # Allow the GUI to update

    '''Step 1: Get list of mzml files'''
    mzml_files = [f for f in os.listdir(directory) if f.endswith('.mzML')]

    if len(mzml_files) == 0:
        update_output(f'There are no mzml files in {directory}. Were they deleted?\n')
        QApplication.processEvents()  # Allow the GUI to update  
        return     

    '''Step 2: Parse power_data.csv file (if present), and assign corresponding photofragmentation efficiency function depending on its presence.'''
    #empty array for PE_calc_NoNorm functions that requires these arguements because ... reasons. Don't worry about it future reader. This is the way. 
    laser_data = np.empty(shape=(len(mzml_files), 3), dtype=[('Wavelength', None),('LaserPower', None), ('PowerStdDev', None)]) 

    #Assisgn method to calcualte photofragmentation efficiency depending on if Power normalization is used or not
    PE_function = PE_calc_noNorm 
    if power_data_file_name is not None: 
        # Load laser data from a CSV file into a structured NumPy array
        laser_data = np.genfromtxt(power_data_file_name, delimiter=',', dtype=None, names=['Wavelength', 'LaserPower', 'PowerStdDev'], encoding=None)
        PE_function = PE_calc
    
    #check to see if the number of mzml files (ie. the number of wavelengths scanned) matches the number of rows in the laser power data file. If not, we'll have index errors!
    if len(mzml_files) != len(laser_data['Wavelength']):
        update_output(f'The number of mzml files ({len(mzml_files)}) does not match the number of rows in the laser power data file ({len(laser_data["Wavelength"])}).\n')
        QApplication.processEvents()  # Allow the GUI to update  
        return
    
    '''Step3: Get the m/z of each fragmentation channel and create arrays for PE data to be written to'''
    #Get central value of fragment ion ranges and mass of parent peak
    parent_mz = (np.round(np.average(base_peak_range),2))
    frag_mz = []
    for frag_ion_range in fragment_ion_ranges:
        frag_mz.append(np.round(np.average(frag_ion_range),0))  

    # Create an empty NumPy array for the final results to be written to
    num_fragment_ions = len(fragment_ion_ranges)
    
    #array size (rows x columns) to store photofragmentation efficiency (PE) data should be number of wavelengths x number of fragment ions * 2 (PE + stdev) + 2 (total PE + stdev) +1 (wavelengths)
    PE_data = np.empty(shape=(len(mzml_files), num_fragment_ions * 2 + 3), dtype=float) 

    '''Step4: Loop through each mzml file in the directory and calculate the fragmentation efficiency for each fragment specified'''
    wavelengths = [] #empty list to store wavlengths to - wavelength written as last characters in each .mzML file
    i = 0 #index to keep track of which row of the power normalization file that we are in

    for mzml_file in mzml_files: #Each mzML file is data taken at a specific laser wavelength
        
        #get laser wavelength from mzml filename and append to list - need that for writing to the final .csv later
        try:
            wavelength = float(re.findall(r'\d+',mzml_file.split('Laser')[-1])[-1]) 
            wavelengths.append(wavelength)
        except ValueError as ve:
            update_output(f'Could not extract the wavelength from the .mzml file name. This is what the code has found: {wavelength}.\n\nDoes the filename contain the text: "Laser"?\n')
            update_output(f'Error: {ve}\nTraceback: {traceback.format_exc()}\n')
            QApplication.processEvents()  # Allow the GUI to update        
            return     

        #empty lists to store the average integrations and their stdev for each fragment - we need these to calcualte the total PE later.  
        fragment_ion_integrations = [] 
        fragment_ion_integrations_stdevs = []

        fragment_ion_efficiencies = [] #empty list to store PE for each fragmentation channel
        fragment_ion_efficiency_stdevs = [] #empty list to store PE stdev for each fragmentation channel

        mzml_start_time = time.time() #timer to keep track of mzml processing

        #get integration for base peak (parent ion)
        try:
            base_peak = integrate_spectra(directory, mzml_file, base_peak_range, parent_mz)

        except Exception as e:
            update_output(f'Problem encountered when integrating the base peak in {mzml_file}:\n{e}\nTraceback: {traceback.format_exc()}\n')
            QApplication.processEvents()  # Allow the GUI to update        
            return     
        
        '''Step4.1: Integrate the mass spectrum to get the integrations of the parent ion peak and each fragment ion peak'''
        for fragment_ion_range in fragment_ion_ranges:
            try:
                fragment_peak = integrate_spectra(directory, mzml_file, fragment_ion_range, parent_mz)
            except Exception as e:
                update_output(f'Problem encountered when integrating the fragment m/z={np.round(np.mean(fragment_ion_range),1)}) in {mzml_file}:\n{e}\nTraceback: {traceback.format_exc()}\n')
                QApplication.processEvents()  # Allow the GUI to update        
                return     

        #print runtime to GUI window        
        mzml_runtime = np.round((time.time() - mzml_start_time),2)
        update_output(f'Integration for {np.round((wavelength),0)}nm has completed in {mzml_runtime} seconds.\n')
        QApplication.processEvents()  # Allow the GUI to update
        
        '''Step 4.2: Calculate PE for each fragment ion, then append PE to the fragment_ion_efficiencies list'''
        
        for fragment_ion_range in fragment_ion_ranges:    
            try:
                PE = PE_function(wavelength, laser_data['LaserPower'][i], laser_data['PowerStdDev'][i], base_peak[0], base_peak[1], fragment_peak[0], fragment_peak[1]) # W, P, dP, Par, dPar, Frag, dFrag
            
            except IndexError:
                update_output('The number of wavelengths sampled in your powerdata.csv file does not match the number of .mzML files extracted. These need to be the same.\n')
                update_output(f"There are {len(mzml_files)} .mzML files in {directory} and {len(laser_data['LaserPower'])} wavelengths in {power_data_file_name}.\nTraceback: {traceback.format_exc()}\n")
                QApplication.processEvents()  # Allow the GUI to update       
                return
            
            except Exception as e:
                update_output(f'Problem encountered when calculating the photofragmentation efficiency of m/z={np.round(np.mean(fragment_ion_range),1)}) in {mzml_file}:\n{e}\nTraceback: {traceback.format_exc()}\n')
                QApplication.processEvents()  # Allow the GUI to update        
                return     

            #Since there are multiple fragmentation channels, append the PE from each channel to a list
            #The PE_function returns a list - the first entry is the photofragmentation efficiency averaged over N spectra; the second entry is the associated stdev
            fragment_ion_efficiencies.append(PE[0]) 
            fragment_ion_efficiency_stdevs.append(PE[1])

            #Since total PE is not the sum of the PE from all fragment channels, we need to store the total integration of all fragment ion peaks and their stdevs
            fragment_ion_integrations.append(fragment_peak[0]) #storing total fragment ion area to calculate total PE later
            fragment_ion_integrations_stdevs.append(fragment_peak[1]) #storing total fragment ion area stdev to calculate total PE stdev later

        '''Step4.3: Compute the total photofragmentation efficiency'''    
        #get total fragment ion integration 
        total_fragment_ion_integration = np.sum(fragment_ion_integrations)

        #propagate stdev of each fragment ion uncertainty together. Since its jsut addition, proparation is the square root of the sum of squares
        total_fragment_ion_integration_stdev = np.sqrt(np.sum(np.square(fragment_ion_integrations_stdevs)))

        #compute total PE for each mzml file
        try:
            Total_PE = PE_function(wavelength, laser_data['LaserPower'][i], laser_data['PowerStdDev'][i], base_peak[0], base_peak[1], total_fragment_ion_integration, total_fragment_ion_integration_stdev) # W, P, dP, Par, dPar, Frag, dFrag
        
        except IndexError:
            update_output('The number of wavelengths sampled in your powerdata.csv file does not match the number of .mzML files extracted. These need to be the same.\n')
            update_output(f"There are {len(mzml_files)} .mzML files in {directory} and {len(laser_data['LaserPower'])} wavelengths in {power_data_file_name}.\n")
            QApplication.processEvents()  # Allow the GUI to update       
            return
        
        except Exception as e:
            update_output(f'Problem encountered when calculating the TOTAL photofragmentation efficiency in {mzml_file}:\n{e}\n')
            QApplication.processEvents()  # Allow the GUI to update        
            return   

        '''Step4.3: Store calculated efficiencies in the result_data array. row index = i'''  
        PE_data[i, 0] = wavelengths[i] #wavelengths in first column
        PE_data[i, 1] = Total_PE[0] # Store total_efficiency in the second column
        PE_data[i, 2] = Total_PE[1] # Store total_efficiency stdev in the third column       
        PE_data[i, 3:num_fragment_ions*2 + 3:2] = fragment_ion_efficiencies # Store fragment ion efficiency in the 4, 6, 8, 10, .... columns
        PE_data[i, 4:num_fragment_ions*2 + 3:2] = fragment_ion_efficiency_stdevs # Store fragment ion efficiency stdev in the 5, 7, 9, 11, .... columns

        i+=1 #update index to start next row of laser data file when the next mzml file is read in

    '''Step5: Create an array to write PE data to'''
    # Create a structured array for results
    dtype = [('Wavelength', float)]
    dtype.extend([('Total PE', float)])
    dtype.extend([('Total PE stdev', float)])

    #Alternate labels for Frag PE and Frag PE stdev
    for i in range(num_fragment_ions): 
        dtype.extend([(f'PE mz {frag_mz[i]}', float)])
        dtype.extend([(f'PE mz {frag_mz[i]} stdev', float)])

    #python magic that I figured out at one point to make a structured data array, but I forget how this works now, so good luck. 
    try:
        result_structured = np.array(list(zip(*[PE_data[:, i] for i in range(PE_data.shape[1])])), dtype=dtype)

    except Exception as e:
        update_output(f'Problem encountered when creating structured data array in main.py:\n{e}\nTraceback: {traceback.format_exc()}')
        QApplication.processEvents()  # Allow the GUI to update        
        return    

    '''Step6: Write the PE data to a .csv file'''
    output_file = os.path.join(os.path.dirname(directory),'photofragmentation_efficiency.csv')
    index = 0

    #mechanism to prevent overwriting existing output files
    while os.path.exists(output_file):
        index += 1
        output_file = os.path.join(os.path.dirname(directory),f'photofragmentation_efficiency_{index}.csv')

    try:
        np.savetxt(output_file, result_structured, delimiter=',', fmt='%.6f', header=','.join(result_structured.dtype.names), comments='')
        update_output(f'The photofragmentation efficiency data has been succesfully written to {output_file}\n\n')
        return

    except PermissionError: #this should never proc because we check for existing files and change the ending index to make sure the file is new, but you never know...
        print(f'Python is trying to write to {output_file}, but it is open. Please close it and then rerun the code.')
        QApplication.processEvents()  # Allow the GUI to update       
        return

