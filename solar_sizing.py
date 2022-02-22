
import os
import io
import math
import functools
import urllib
import datetime
import streamlit as st
import pandas as pd
import numpy as np
import requests

import matplotlib.pyplot as plt

# Most of the data files are located remotely and are retrieved via
# an HTTP request.  The function below is used to retrieve the files,
# which are Pandas DataFrames

# The base URL to the site where the remote files are located
base_url = 'http://ak-energy-data.analysisnorth.com/'


# # Use some of Alan Mitchells's code from the heat pump calculator (github) to download tmy files for hourly temperature

def get_df(file_path):
    """Returns a Pandas DataFrame that is found at the 'file_path'
    below the Base URL for accessing data.  The 'file_path' should end
    with '.pkl' and points to a pickled, compressed (bz2), Pandas DataFrame.
    """
    b = requests.get(urllib.parse.urljoin(base_url, file_path)).content
    df = pd.read_pickle(io.BytesIO(b), compression='bz2')
    return df

#load a file with tmy summary info including the best tilt for a solar panel:
df = pd.read_csv('AKtmy_summary.csv', parse_dates = True, index_col = 'tmy_id')

#load a file with pvwatts monthly solar production for tmy3 stations in AK, based on tilt:
results_df = pd.read_csv('AKtmy_monthlyprod.csv', parse_dates = True, index_col = 0)
#these are the tilts used:
#tilts = [14,18.4,22.6,26.6,30,45,df['best_tilt'].loc[df.index == tmyid].iloc[0],90] 

st.image(['ACEP.png'])
st.title("Alaska Solar PV Sizing and Payback Calculator")
st.write("")
st.write("This is a calculator to find optimal sizing and economic payback for a behind-the-meter PV system in Alaska.")

st.write("Community and Utility data are taken from http://ak-energy-data.analysisnorth.com/ ")
st.write("Solar modeling is done using https://pvwatts.nrel.gov/ ")
st.write("This calculator assumes no shading and does not account for snow coverage.  Real-life installations will likely not reach this ideal.")

#location
#get the Alaska city data
# Access as a Pandas DataFrame
dfc = get_df('city-util/proc/city.pkl')

# User Input

#create a drop down menu of the available communities and find the corresponding TMYid
cities = dfc['aris_city'].drop_duplicates().sort_values(ignore_index = True) #get a list of community names
city = st.selectbox('Select your community:', cities ) #make a drop down list and get choice
tmyid = dfc['TMYid'].loc[dfc['aris_city']==city].iloc[0] #find the corresponding TMYid

#User input: choose a tilt, enter cost info, etc:
tilts = [14,18.4,22.6,26.6,30,45,df['best_tilt'].loc[df.index == tmyid].iloc[0],90]

tilt = st.selectbox('Choose a tilt in degrees for your panels:', tilts ) #make a drop down list and get choice
st.write("Note: the first 4 choices correspond to roof slopes of 3 in 12, 4 in 12 etc.  The second to last choice is the optimum tilt for your location according to NREL's PVWatts calculator. 90 degrees is vertical.")
st.write("")
taxr = st.selectbox('Select a solar tax credit amount, 26% for installation in 2022, 22% for 2023:', [26,22] )/100 #make a drop down list and get choice.26 #26 in 2022, 22% in 2023

life = st.slider('What is the life of your system in years?', max_value = 30, value = 20)
cost = st.slider('What is the cost of your system in $ per installed watt (this may depend on the size of the system)?', max_value = 9.00, value = 3.00)
def_size = 3.0 #will need this later if not a net metered system


#find the production at that tilt and location:
unit_prod = results_df.loc[(results_df['tmy_id'] == tmyid) & (results_df['tilt'] == tilt)].iloc[0,2:]
unit_prod.index = unit_prod.index.astype(int)-1

#There are two very different situations - net metered or non-netmetered!

# Access Alan's Alaska utility data as a Pandas DataFrame
dfu = get_df('city-util/proc/utility.pkl')
util = dfc['ElecUtilities'].loc[dfc['aris_city']==city].iloc[0][0][1] #find a utility id for the community chosen
uname = dfc['ElecUtilities'].loc[dfc['aris_city']==city].iloc[0][0][0] #find the utility name for the community chosen
uname = uname.split('-')[0] #that name had a rate class included, so breaking that off - check if this works!
if (dfu['PCE'].loc[dfu['ID']==util].iloc[0]==dfu['PCE'].loc[dfu['ID']==util].iloc[0]): #if utility has a PCE adjusted rate, use it
    rate_def = dfu['PCE'].loc[dfu['ID']==util].iloc[0]
else: #otherwise dig down for the non-PCE adjusted rate
    rate_def = dfu['Blocks'].loc[dfu['ID']==util].iloc[0][0][1] #at least for fairbanks this works to get a per kWh rate from the database - may not always work!

rate_def = float(rate_def) #the slider later didn't like the numpy.float64
cpkwh_default = dfu['CO2'].loc[dfu['ID']==util].iloc[0]/2.2 #find the CO2 per kWh for the community and divide by 2.2 to change pounds to kg
cpkwh_default = float(cpkwh_default) 
st.write("")
#st.write("According to the database, your utility is ", uname) #if I keep this in will have to deal with the fact that ANC is listed as ML&P!
st.write("Always talk to your utility before adding grid-connected solar!  Each utility has its own process, and some may not be equiped to safely allow electricity to flow back on to the grid.")
st.write("Golden Valley Electric, Matanuska Electric, Chugach Electric, Seward Electric and Homer Electric allow net metering, with certain limits and an interconnection agreement")

nm = st.checkbox("Check here if your utility will allow your system to net-meter")
if nm:
    

    #choose an electric rate, avoided fuel cost,netmetered?, system life, system cost,  monthly usage
    rate = st.slider('What do you pay per kWh for electricity?', max_value = 1.0, value = rate_def)
    st.write("Note: we do not account for PCE limits, block rates, or demand charges, which could change the results.")
    copa = st.slider('What is the avoided fuel cost for your utility?', max_value = .20, value = .08)
    st.write("To find this, check at your utility's website or call the utility customer service. This is the amount assumed to be payed for electricity sold back to your utility.")
    st.write("Input your monthly electric usage in kWh (from your bills or utility member portal) here:")
    u1 = st.number_input('January:', min_value = 0, value = 300)
    u2 = st.number_input('Febuary:',min_value = 0,value = 300)
    u3 = st.number_input('March:',min_value = 0, value = 300)
    u4 = st.number_input('April:',min_value = 0, value = 300)
    u5 = st.number_input('May:',min_value = 0, value = 300)
    u6 = st.number_input('June:',min_value = 0, value = 300)
    u7 = st.number_input('July:',min_value = 0, value = 300)
    u8 = st.number_input('August:',min_value = 0, value = 300)
    u9 = st.number_input('September:',min_value = 0, value = 300)
    u10 = st.number_input('October:',min_value = 0, value = 300)
    u11 = st.number_input('November:',min_value = 0, value = 300)
    u12 = st.number_input('December:',min_value = 0, value = 300)
    usage = pd.Series([u1,u2,u3,u4,u5,u6,u7,u8,u9,u10,u11,u12])
    
    #some calulations:
    max_size = usage/unit_prod #element-wise array calc
    def_size = round(float(min(max_size)),1)
size = st.slider('Size of the system in kW(the default here is the system with the best payback if you have net metering)?', max_value = 25.0, value = def_size)
prod = size*unit_prod 


#more calcs - will want to present:
cost_sys = cost * size*1000
st.write("Expected System Cost: $", round(cost_sys,2))
tcredit = cost_sys * taxr
st.write("Expected Tax Credit: $", round(tcredit,2))
net_cost = cost_sys - tcredit
st.write("Expected Net System Cost: $", round(net_cost,2))
st.write("Expected System Production in kWh:", round(sum(prod),0))
if nm:
    save = rate*prod #only true if net metering and for this prod l.t. consumpt
    #for net metered - where prod < usage, save = rate*prod, where prod > usage, save = usage*rate + copa*(prod - usage)
    save.where(prod < usage, usage*rate + copa*(prod-usage), inplace = True)
    annual_save = sum(save)
    st.write("Expected Annual Energy Cost Savings:$", round(annual_save,2))
    simplepay = net_cost/annual_save
    st.write("Simple Payback in Years:", round(simplepay,1))
    annualROI = ((1+((life*annual_save)-net_cost)/net_cost)**(1/life)-1)*100
    st.write("Annualizaed ROI:", round(annualROI,1),"%")
    grid_red = sum(prod)/sum(usage)*100
    st.write("Reduction in Grid Energy Usage:", round(grid_red,1),"%")


    x = ['J','F','M','A','M','J','J','A','S','O','N','D']
    fig, ax = plt.subplots()
    ax.bar(x,prod, width=-0.35, align='edge', label = 'Solar Production')
    ax.bar(x,usage, width=0.35, align='edge', label = 'Household Consumption')
    # Add the axis labels
    ax.set_xlabel('Month')
    ax.set_ylabel('kWh')

    # Add in a legend and title
    ax.legend(loc = 'upper right')
    #ax.title('')
    st.pyplot(fig)



#could calculate NPV etc, take into account utility rate escalation, inflation, and degradation - maybe a little much for now!

# could look at greenhouse gas emission reductions in the future 


st.write("")
st.write("This calculator was written in excel by Ben Loeffler and adapted to streamlit by Michelle Wilber.  Any errors are the fault of the adaptation")
st.write("Thanks to Alan Mitchell of Analysis North for Alaskan utility data, tmy files, and wonderful code to access and use them all.")
st.write("See http://ak-energy-data.analysisnorth.com and https://github.com/alanmitchell/heat-pump-calc")
st.write("...And definitely check out the Alaskan Heat Pump Calculator at https://heatpump.cf to see if you should get a heat pump!")
st.write("")
st.write("")
st.write("Please peak under the hood at this code at https://github.com/mmwilber/AKSolar-Calculator")
st.write("Solar production is modeled via PVWatts assuming standard modules in a fixed open rack facing due south at the chosen tilt and using a nearby TMY3 station.  Losses are set to 14%, and other parameters are PVWatts defaults.")
st.write("email Michelle Wilber at mmwilber@alaska.edu with any suggestions or comments.")
