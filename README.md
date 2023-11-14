# UVPD_Analysis_GUI
A GUI and sample files for analysis of variable wavelength UVPD data obtained on the modified QTRAP 5500 hybrid triple-quad in the Hopkins Lab


Launch the GUI by running UVPD_GUI.py (found in the GUI directory) in your preferred Python environment. Note that this GUI requires the following packages: PyQt5, numpy, pandas, and pyteomics. If you are missing any of these, you will be prompted to install them on launch directly on launch. 

Once initialized, the interface can be popluated with the following fields:

Directory: The directory that contains the .wiff files. As a naming convention, each scan that is saved to the .wiff file contains a substring 'Laser_On_XXXnm', where XXX is the wavelength of the laser light being used for UVPD. The directory can be selected using an Explorer-like interface by clicking on the "Select Directory" option. 

Base Peak Range: the upper and lower m/z value that encompasses the parent ion peak. This entry should be two, comma-separated numbers. The numbers can be intergers or decimals. For example: 202.5,204
Fragment Ion Ranges: the upper and lower m/z value that encompasses each fragment ion formed via UVPD. This entry can contain as many fragments as you wish. The format for entry is two, comma-separated numbers enclosed by comma-separated brackets. The numbers can be intergers or decimals. For example: (50.5,51.5),(102.5,103.5),125.5,127.9)

The Extract mzML files from .wiff checkbox: If checked, .mzML files will be created for all scans saved to each .wiff files found in the Directory. If unchecked, the code will look for .mzML files in the mzML directory, which will have the path Directory\\mzml_directory. This mzML directory is automatically created if the Extract mzML files from .wiff checkbox is checked. 

The Normalize to Laser Power checkbox: If checked, normalizes photofragmentation efficiency to laser power (reccomended; see https://pubs.acs.org/doi/full/10.1021/acs.jpca.1c05564). If unchecked, photofragmentation efficiency will not be normalized to laser power (not reccomended). The name of the powerdata.csv file is provided in the corresponding dialog box. 

The Print Raw Data checkbox: If selected, the full mass spectrum for each scan found in the .wiff file will be printed to a .csv. 

For proper file format and naming conventions, please see the example files provided in the ExampleData_beforeAnalysis and ExampleData_afterAnalysis directories. 

# Example Usage

The GUI can be run on the data provided in the ExampleData_beforeAnalysis directory. The GUI can be popluated with thet following information, which should mimic the outputs found in the ExampleData_afterAnalysis directory

Base peak range: 239.0,242.0

Fragment ion ranges: (54.5,57.0),(114.5,116.0),(129.5,131.0),(139.5,140.5),(141.5,142.8),(153.5,154.5),(156.5,158.0),(167.5,169.0),(170.5,172.0),(180.5,181.8),(182.6,184.0),(184.5,186.0),(198.5,200.0),(208.0,210.0)

Power data filename: powerscan_400_600nm_120us.csv

Please report any bugs to the issues section. 
