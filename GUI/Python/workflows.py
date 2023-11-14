import os, re, sys, traceback, subprocess
import numpy as np
import pyteomics.mzml as mzml
import pandas as pd
from PyQt5.QtWidgets import QApplication
from io import StringIO

class TextRedirect(StringIO):
    def __init__(self, textWritten=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_output = textWritten

    def write(self, text):
        super().write(text)
        self.update_output(text)

def convert_wiff_to_mzml(wiff_file, directory, mzml_directory, update_output=None):
    ''' Function to convert .wiff files to .mzml using msconvert
    input is .wiff file, directory that contains .wiff files, and directory to output mzml files to'''
    
    # Redirect print outputs to the GUI output window
    sys.stdout = TextRedirect(textWritten=update_output)

    mzml_file = f'{os.path.splitext(wiff_file)[0]}.mzml'
    
    try:
        subprocess.run(['msconvert', os.path.join(directory, wiff_file), '-o', mzml_directory, '--mzML', '--64'])
        return mzml_file
    
    except subprocess.CalledProcessError as cpe:
        update_output(f'Subprocess error converting {wiff_file} to mzML: {cpe}\nTraceback: {traceback.format_exc()}\n')
        QApplication.processEvents()  # Allow the GUI to update        
        raise subprocess.CalledProcessError('msconvert command failed during .wiff file conversion.')

    except Exception as e:
        update_output(f'Unexpected error converting {wiff_file} to mzML: {e}\nTraceback: {traceback.format_exc()}\n')
        QApplication.processEvents()  # Allow the GUI to update        
        raise Exception('Unexpected error during .wiff file conversion.')
    
# Function to integrate mass spectra within specified bounds using NumPy
def integrate_spectra(directory, mzml_file, integration_bounds, parent_mz, update_output=None):
    '''Integrates the mass spectra from mzml files and averages them across all scans. Interpolation on a common mz grid for all mzml files provided is used. Usage is:
    directory containing mzml files, name of mzml file, integration bounds [as a list], and the m/z of the parent ion (needed for interpolation).
    '''
    # Redirect print outputs to the GUI output window
    sys.stdout = TextRedirect(textWritten=update_output)

    #Initialize lists to integrations, and variables for minimum and maximum m/z values
    integrations = []
    min_mz = 0.
    max_mz = parent_mz + 50.  #adding 50 mass units to the parent ion

    #define common mz grid for interpolation
    common_mz_grid = np.round(np.linspace(min_mz, max_mz, int((max_mz - min_mz) / 0.01 + 1)),2) #0.01 Da incremenets for mz grid

    with mzml.read(os.path.join(directory, mzml_file)) as spectra:
        i = 0        
        for spectrum in spectra:

            #according to stack exchange, these are pre-defined lists from pyteomics              
            try:
                mz = spectrum['m/z array']
                intensity = spectrum['intensity array']
                
                #get min and max values from the mzml mz list
                min_mz_mzml = np.min(mz)
                max_mz_mzml = np.max(mz)   

            except Exception as e:
                update_output(f'Error encounter when extract m/z and intensity arrays from spectrum number {i+1} in {mzml_file}: {e}.\nTraceback: {traceback.format_exc()}\n')
                QApplication.processEvents()  # Allow the GUI to update 
                raise Exception('mzML data extraction error.') 
            
            # Check for inconsistent data
            if len(mz) != len(intensity):
                update_output(f'Inconsistent lengths of m/z and intensity values when integrating {mzml_file}\n')
                QApplication.processEvents()  # Allow the GUI to update     
                raise ValueError('Value error!')
            
            #Filter out values in the common_mz_grid are are within the mz values taken from the mzml file, then define a new set of mz_values 
            mask = (common_mz_grid < min_mz_mzml) | (common_mz_grid > max_mz_mzml)
            new_mz_values = common_mz_grid[mask]
            
            # Append the new values to the mz array from the mzml file with correponding intensity of zero
            mz = np.append(mz, new_mz_values)
            intensity = np.append(intensity, np.zeros(len(new_mz_values)))

            #Sort the arrays based on increasing mz
            sort_indices = np.argsort(mz)
            mz = mz[sort_indices]
            intensity = intensity[sort_indices]
                    
            #now interpolate using
            try:
                interp_intensity = np.interp(common_mz_grid, mz, intensity)
            
            except ValueError as ve:
                update_output(f'ValueError encountered during interpolation of the spectra within {mzml_file}: {ve}\nTraceback: {traceback.format_exc()}\n')
                QApplication.processEvents()  # Allow the GUI to update      
                raise ValueError('Interpolation error')
                
            except Exception as e:
                update_output(f'Unexpected error encountered during interpolation of the spectra within {mzml_file}: {e}\nTraceback: {traceback.format_exc()}\n')
                QApplication.processEvents()  # Allow the GUI to update      
                raise Exception('Interpolation error')
            
            #Define integration bounds as the indicies within the common m/z grid 
            try:
                lower_bound = np.round(integration_bounds[0],2)
                upper_bound = np.round(integration_bounds[1],2)
                filter = (common_mz_grid >= lower_bound) & (common_mz_grid <= upper_bound)

                #only take mz and intensity data from within the integration bounds
                mz_interval = common_mz_grid[filter]
                interp_intensity_interval = interp_intensity[filter]
                
                # Integrate within specified bounds using NumPy trapz, and append each integration to the integrations list; its not a trap, I swear. 
                integration = np.trapz(interp_intensity_interval, x = mz_interval)
                integrations.append(integration)

                i+=1

            except ValueError as ve:
                update_output(f'ValueError encountered during integration of the spectra within {mzml_file}: {ve}\nTraceback: {traceback.format_exc()}\n')
                QApplication.processEvents()  # Allow the GUI to update      
                raise ValueError('Integration error')    
                    
            except Exception as e:
                update_output(f'Error encountered during integration of the spectra within {mzml_file}: {e}\nTraceback: {traceback.format_exc()}\n')
                QApplication.processEvents()  # Allow the GUI to update      
                raise Exception('Integration error')

    # Calculate the average integration value. Doing it this way because we need to get standard deviations
    avg_integration = np.mean(integrations)
    std_dev = np.std(integrations)
    
    return [avg_integration, std_dev] 

def extract_RawData(mzml_directory, parent_mz, output_csv_file, update_output=None):
    '''Extracts the mass spectra from mzml files and averages them across all scans. Interpolation on a common mz grid for all mzml files provided is used. Usage is:
    directory containing mzml files, m/z of the parent ion (needed for interpolation), and the name of .csv file to output results to.
    '''

    # Redirect print outputs to the GUI output window
    sys.stdout = TextRedirect(textWritten=update_output)
   
    #Set up interpolation grid - different from before because we don't want to print the mass spectrum in 0.01 Da increments. 
    min_mz = 0.
    max_mz = parent_mz + 50.  #adding 50 mass units to the parent ion

    common_mz_grid = np.round(np.linspace(min_mz, max_mz, int((max_mz - min_mz) / 0.02 + 1)),2) #0.02 Da incremenets for mz grid

    #Get a list of mzML files in the given directory
    mzml_files = [f for f in os.listdir(mzml_directory) if f.endswith('.mzML')]

    #initialize dictionary to write data to
    data_dict = {}
    
    for mzml_file in mzml_files:
        
        #initialize list to store interpolated intensities - this needs to be re-initialized for each new wavelength (i.e., each mzml file)
        interpolated_intensity_values = []

        #get wavelength from mzml file name
        try:
            wavelength = re.findall(r'\d+', mzml_file.split('Laser')[-1])[-1]
        except ValueError as ve:
            update_output(f'Could not extract the wavelength from the .mzml file name. This is what the code has found: {wavelength}.\nDoes the filename contain the text: "Laser"?\n')
            update_output(f'Error: {ve}\nTraceback: {traceback.format_exc()}\n')       
            QApplication.processEvents()  # Allow the GUI to update 
            raise ValueError('ValueError')    

        #Open up the .mzml file, extract the mass spectrum, and perform the interpolation
        i = 0
        with mzml.read(os.path.join(mzml_directory, mzml_file)) as spectra:
            for spectrum in spectra:
                #according to stack exchange, these are pre-defined lists from pyteomics
                try:
                    mz = spectrum['m/z array']
                    intensity = spectrum['intensity array']
                
                except Exception as e:
                    update_output(f'Error encounter when extract m/z and intensity arrays from spectrum number {i+1} in {mzml_file}: {e}.\nTraceback: {traceback.format_exc()}\n')
                    QApplication.processEvents()  # Allow the GUI to update 
                    raise Exception('mzML data extraction error.')                            
                
                #get min and max values from the mzml mz list
                min_mz_mzml = np.min(mz)
                max_mz_mzml = np.max(mz)
                
                #Check for inconsistent data
                if len(mz) != len(intensity):
                    update_output(f'Inconsistent data in {mzml_file}.\n The m/z and intensity arrays extracted from the .mzML file must be the same length!\n')
                    QApplication.processEvents()  # Allow the GUI to update 
                    raise ValueError(f'ValueError')
                
                #Create filter based on a common mz grid
                mask = (common_mz_grid < min_mz_mzml) | (common_mz_grid > max_mz_mzml) # the "|" denotes "or"

                # Filter common_mz_grid based on the mask
                new_mz_values = common_mz_grid[mask]
                
                # Append the new values to mz with correponding intensity of zero
                mz = np.append(mz, new_mz_values)
                intensity = np.append(intensity, np.zeros(len(new_mz_values)))

                #Sort the arrays based on increasing mz
                sort_indices = np.argsort(mz)
                mz = mz[sort_indices]
                intensity = intensity[sort_indices]
                        
                #now interpolate
                try:
                    interp_intensity = np.interp(common_mz_grid, mz, intensity)
                    interpolated_intensity_values.append(interp_intensity)
                    i += 1            

                except ValueError as ve:
                    update_output(f'ValueError encountered during interpolation of the spectra within {mzml_file}: {ve}\nTraceback: {traceback.format_exc()}\n')
                    QApplication.processEvents()  # Allow the GUI to update      
                    raise ValueError('Interpolation error')
                    
                except Exception as e:
                    update_output(f'Unexpected error encountered during interpolation of the spectra within {mzml_file}: {e}\nTraceback: {traceback.format_exc()}\n')
                    QApplication.processEvents()  # Allow the GUI to update      
                    raise Exception('Interpolation error')

        # Step 16: Calculate the averaged spectrum across each scan for this mzML file
        averaged_spectrum = np.mean(interpolated_intensity_values, axis=0)
        data_dict[wavelength] = averaged_spectrum
    
    # Step 17: Create a DataFrame with the common m/z grid as the first column
    df = pd.DataFrame(data_dict)
    df.insert(0, "m/z", common_mz_grid)

    # Step 18: Write the DataFrame to a CSV file
    try: 
        df.to_csv(output_csv_file, index=False)
        update_output(f'Data succesfully written to {output_csv_file}\n\n')
        QApplication.processEvents()  # Allow the GUI to update  
        return
    
    except PermissionError:
        'Close the .csv file with the same name as the one where the raw data is being written and then rerun the code.\n'
        return

def PE_calc(W, P, dP, Par, dPar, Frag, dFrag, update_output=None):
    '''Calculates photofragmentation efficiency with normlaization to laser power. Useage is:
    Wavelength, Power, Power stdev, base peak integration, base peak integration stdev, fragment peak integration, fragment peak integration stdev
    '''

    # Check for division by zero
    if P == 0 or Par + Frag == 0:
        update_output(f'Division by zero error for wavelenth {W}nm. Power (P) is {P}, Parent integration is {Par} and Fragment integration is {Frag}.\n The sum of base peak integration (Par) and fragment peak integration (Frag) must be non-zero.\nTraceback: {traceback.format_exc()}\n')
        QApplication.processEvents()  # Allow the GUI to update   
        raise ValueError('Value Error')
   
    dW = 2 #bandwidth of OPO - assuming that it is +/- 2 nm
        
    #calculate photofragmentation efficiency
    efficiency = -(W / P) * np.log(Par / (Frag + Par))

    #calculate standard deviatian in photofragmentation efficiency
    try:
        term1 = np.square((np.log(Par / (Par + Frag)) / -P) * dW)
        term2 = np.square(((W * np.log(Par / (Par + Frag))) / np.square(P)) * dP)
        term3 = np.square(-1 * ((1 / (Par + Frag) / P / Par * W * Frag)) * dPar)
        term4 = np.square((W * 1 / (Par + Frag) / P) * dFrag)

        PE_stdev = np.sqrt(term1+term2+term3+term4)

        return [efficiency, PE_stdev]    
    
    except Exception as e:
        update_output(f'Error encountered during calculation of photogfragmentaion efficiency at wavelength {W}nm: {e}\nTraceback: {traceback.format_exc()}\n')
        QApplication.processEvents()  # Allow the GUI to update      
        raise Exception('Photofragmentation efficiency calculation error')

def PE_calc_noNorm(W, P, dP, Par, dPar, Frag, dFrag, update_output=None): 
    '''Calculates photofragmentation efficiency without normlaization to laser power. Useage is:
    Wavelength, Power, Power stdev, base peak integration, base peak integration stdev, fragment peak integration, fragment peak integration stdev
    Note that W, P, and dP are dummy variables - kept it like this for functionality within main().
    '''
    
    # Check for division by zero
    if Par + Frag == 0:
        update_output(f'Division by zero error for wavelenth {W}nm. Power (P) is {P}, Parent integration is {Par} and Fragment integration is {Frag}.\n The sum of base peak integration (Par) and fragment peak integration (Frag) must be non-zero.\nTraceback: {traceback.format_exc()}\n')
        QApplication.processEvents()  # Allow the GUI to update     
        raise ValueError('Value Error')

    #calculate photofragmentation efficiency
    efficiency = -1 * np.log(Par / (Frag + Par))

    #calculate standard deviatian in photofragmentation efficiency
    try:
        term1 = np.square(-1 * (Frag / (Par + Frag) / Par) * dPar)
        term2 = np.square((1 / (Par + Frag)) * dFrag)

        PE_stdev = np.sqrt(term1+term2)
        
        return [efficiency, PE_stdev]

    except Exception as e:
        update_output(f'Error encountered during calculation of photogfragmentaion efficiency at wavelength {W}nm: {e}\nTraceback: {traceback.format_exc()}\n')
        QApplication.processEvents()  # Allow the GUI to update      
        raise Exception('Photofragmentation efficiency calculation error')