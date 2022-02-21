
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

#import matplotlib.pyplot as plt

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
df = pd.read_csv('/drive/My Drive/Electric Vehicles/EV Solar/AKtmy_summary.csv', parse_dates = True, index_col = 'tmy_id')

#load a file with pvwatts monthly solar production for tmy3 stations in AK, based on tilt:
results_df = pd.read_csv('/drive/My Drive/Electric Vehicles/EV Solar/AKtmy_monthlyprod.csv', parse_dates = True, index_col = 0)
#these are the tilts used:
#tilts = [14,18.4,22.6,26.6,30,45,df['best_tilt'].loc[df.index == tmyid].iloc[0],90] 

st.image(['ACEP.png'])
st.title("Alaska Solar PV Sizing and Payback Calculator")
st.write("")
st.write("This is a calculator to find optimal sizing and economic payback for a behind-the-meter PV system in Alaska.")
st.write("A comparison is also made to an internal combustion engine (ICE) vehicle.")
st.write("Community and Utility data are taken from http://ak-energy-data.analysisnorth.com/ ")

#location
#get the Alaska city data
# Access as a Pandas DataFrame
dfc = get_df('city-util/proc/city.pkl')

#now create a drop down menu of the available communities and find the corresponding TMYid
cities = dfc['aris_city'].drop_duplicates().sort_values(ignore_index = True) #get a list of community names
city = st.selectbox('Select your community:', cities ) #make a drop down list and get choice
tmyid = dfc['TMYid'].loc[dfc['aris_city']==city].iloc[0] #find the corresponding TMYid

#get the tmy for the community chosen:
#tmy = tmy_from_id(tmyid)
#note: the temperatures are in F :)


# User Input


#choose a tilt
#choose an electric rate, avoided fuel cost,netmetered?, system life, system cost,  monthly usage 
tilt = 45
rate = st.slider('What do you pay per kWh for electricity?', max_value = 1.0, value = .2)
st.write("Note: we do not account for PCE, block rates, or demand charges, which could change the results.")
copa = st.slider('What is the avoided fuel cost for your utility?', max_value = .50, value = .7)
st.write("This is the amount assumed to be payed for electricity sold back to your utility.")
taxr = .26 #26 in 2022, 22% in 2023
life = 20
cost = 3.00
usage = pd.Series([600,600,500,400,400,300,300,400,500,500,600,600])

#find the production at that tile and location:
unit_prod = results_df.loc[(results_df['tmy_id'] == tmyid) & (results_df['tilt'] == tilt)].iloc[0,2:]
unit_prod.index = unit_prod.index.astype(int)-1
#some calulations:
max_size = usage/unit_prod #element-wise array calc
def_size = min(max_size)
size = def_size #the default
size = 5
prod = size*unit_prod 

save = rate*prod #only true if net metering and for this prod l.t. consumpt
#for net metered - where prod < usage, save = rate*prod, where prod > usage, save = usage*rate + copa*(prod - usage)
save.where(prod < usage, usage*rate + copa*(prod-usage), inplace = True)
#more calcs - will want to present as a table:
cost_sys = cost * size
tcredit = cost_sys * taxr
net_cost = cost_sys - tcredit
annual_save = sum(save)
simplepay = net_cost/annual_save
anualROI = (1+((life*annual_save)-net_cost)/net_cost)**(1/life)-1
grid_red = sum(prod)/sum(usage)


weekend = (st.slider('How many miles do you drive each weekend day, on average?', value = 10))/2

st.write("Total yearly miles driven:", tmy['miles'].sum())

#add a garage option for overnight parking
garage = st.checkbox("I park in a garage overnight.")
if garage:
    Temp_g = st.slider('What temperature is your garage kept at in the winter?', value = 50, max_value = 80)



st.write("") #after being just fine, this was looking wrong - adding some spaces to try to keep text from overlapping

epm = st.slider('Enter the Rated kWh/mile of the EV to investigate '
                '(this calculator internally adjusts for the effect of temperature): '
                'A 2017 Bolt is .28 according to fueleconomy.gov', value = .28, max_value = 3.0)


#total cost to drive EV for a year:

total_cost_ev = coe*tmy.kwh.sum()

#greenhouse gas emissions from electricity:
# Access Alan's Alaska utility data as a Pandas DataFrame
dfu = get_df('city-util/proc/utility.pkl')

util = dfc['ElecUtilities'].loc[dfc['aris_city']==city].iloc[0][0][1] #find a utility id for the community chosen
cpkwh_default = dfu['CO2'].loc[dfu['ID']==util].iloc[0]/2.2 #find the CO2 per kWh for the community and divide by 2.2 to change pounds to kg
cpkwh_default = float(cpkwh_default)
st.write("")
cpkwh = st.slider("How many kg of CO2 are emitted per kWh for your utility "
                  "(if you don't know, leave it at the default value here, which is specific to your community "
                  "but might be a couple of years out of date."
                  "  Another caveat - the default is based on total utility emissions, but additional electricity may come from a cleaner or dirtier source."
                  "  For instance, in Fairbanks, any new electricity is likely to be generated from Naptha, which is cleaner than the utility average,"
                  "  so a better value to use below for Fairbanks might be 0.54)?:", max_value = 2.0, value = cpkwh_default)
pvkwh = 0 #initialize to no pv kwh...
ispv = st.checkbox("I will have solar panels at my home for the purpose of offsetting my EV emissions.")
if ispv:
    pv = st.slider("How many kW of solar will you have installed? (pro tip: this calculator assumes a yearly capacity factor "
                   "of 10%.  This is reasonable for most of Alaska, but if you are an engineering wiz and want to"
                   " correct this slider for the details of your installation, go ahead!)",
                   max_value = 25.0, value = 3.0)
    #at 10% capacity factor this equation below gives the number of PV kWh generated - we will be kind and
    #attribute them all to the EV, subtracting them off of the emissions
    pvkwh = .1*24*365*pv
    st.write("The annual kWh that your solar panels are estimated to generate:", round(pvkwh,3))
    st.write("We will use this to reduce the carbon emissions from your EV electricity.")

#comparison to gas:
mpg = st.slider('What is the mpg of your gas car?', value = 25, max_value = 60)
dpg = st.slider('What is the price of gas per gallon?', value = 3.5, max_value = 10.0)
#make this temperature dependent too like above.
#according to fueleconomy.gov, an ICE can have 15 to 25% lower mpg at 20F than 77F. the 25% is for trips under 3-4 miles, so could adjust the below later for this
#for now I am just using 20% less
tmy['mpg'] = mpg
tmy['mpg'] = tmy['mpg'].where((tmy['db_temp'] > 77), mpg - .2*mpg*(77-tmy['db_temp'])/57)

tmy['gas'] = tmy.miles/tmy.mpg #gallons of gas used for driving a gas car


#what about the engine block heater or idling in the cold?
tmy_12 = tmy[['db_temp']].resample('D', label = 'right').min()
tmy_12['plug'] = 0
tmy_12['plug'] = tmy_12['plug'].where(tmy_12.db_temp > 20, 1)
plug_days = tmy_12.plug.sum()

plug = st.checkbox("I have a block heater on my gas car.")

if plug:
    st.write("This calculator assumes a block heater is used for your gas car any day the minimum temperature has been less than 20F")
    plug_hrs = st.slider("How many hours do you plug in your block heater each day?", max_value = 24, value = 2)
    plug_w = st.slider("How many watts is your block heater (or block plus oil heater)?", min_value = 400, max_value = 1600)
    kwh_block = plug_w/1000*plug_hrs*plug_days
else:
    kwh_block = 0
cost_block = coe*kwh_block
idle = st.slider("How many minutes do you idle your gas car on cold days (to warm up or keep your car warm)?", max_value = 500, value = 5)
idleg = .2*idle/60*plug_days #cars use about .2g/hr or more at idle : https://www.chicagotribune.com/autos/sc-auto-motormouth-0308-story.html

total_cost_gas = (tmy.gas.sum()+idleg)*dpg

#now look at ghg emissions:
#Every gallon of gasoline burned creates about 8.887 kg of CO2 (EPA)
ghg_ice = 8.887*(tmy.gas.sum()+idleg)

ghg_ev = cpkwh*(tmy.kwh.sum() - pvkwh)
if ghg_ev < 0:
    ghg_ev = 0

ghg_block = cpkwh*kwh_block

st.write("")
st.write("The effective yearly average kWh/mile for your EV is calculated as ", round(tmy.kwh.sum()/tmy.miles.sum(),2))
st.write("This is lower than the rated kWh/mile - cold temperatures lower the range and driving efficiency, and also lead to energy use to keep the battery warm while parked. ")
st.write("")
st.write("Total cost of EV fuel per year = $", round(total_cost_ev,2))
st.write("Total cost of ICE fuel per year = $", round(total_cost_gas+cost_block,2))
st.write("Total kg CO2 EV per year = ", round(ghg_ev,2))
st.write("Total kg CO2 ICE per year = ", round(ghg_ice + ghg_block,2))
st.write(" ")
st.write("The calculations are based on data for commercially available electric cars, results may not hold for other types of electric vehicles. ")
st.write("Your personal driving habits and other real world conditions could change these results dramatically! ")
st.write("The underlying model relating energy use with temperature will be updated as we continue to collect cold weather EV data. ")
st.write("Thanks to Alan Mitchell of Analysis North for Alaskan utility data, tmy files, and wonderful code to access and use them all.")
st.write("See http://ak-energy-data.analysisnorth.com and https://github.com/alanmitchell/heat-pump-calc")
st.write("...And definitely check out the Alaskan Heat Pump Calculator at https://heatpump.cf to see if you should get a heat pump!")
st.write("")
st.write("")
st.write("Please peak under the hood at this code.  Basically, a typical year's hourly temperature profile is combined with a daily driving profile and realtionships between the energy use for driving and maintaining the EV while parked vs temperature to arrive at a cost and emissions for the kWh needed by the EV.")
st.write("email Michelle Wilber at mmwilber@alaska.edu with any suggestions or comments.")
