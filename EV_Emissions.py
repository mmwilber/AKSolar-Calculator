#ability to choose how long you use block heater, size of block heater, how long idle for ICE
#weekend miles
#assume 30mph (or ask?) and subtract off travel time from parked time.
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

@functools.lru_cache(maxsize=50)    # caches the TMY dataframes cuz retrieved remotely
def tmy_from_id(tmy_id):
    """Returns a DataFrame of TMY data for the climate site identified
    by 'tmy_id'.
    """
    df = get_df(f'wx/tmy3/proc/{tmy_id}.pkl')
    return df

st.title("Alaska Electric Vehicle Calculator")
st.write("This is a calculator to find out how much it would cost to charge an EV at home in Alaska, and what the carbon emissions would be.")
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
tmy = tmy_from_id(tmyid)
#note: the temperatures are in F :)


# # put together a driving profile
owcommute = (st.slider('How many miles do you drive each weekday, on average?', value = 10))/2
weekend = (st.slider('How many miles do you drive each weekend day, on average?', value = 10))/2
tmy['miles'] = 0
#Assume a 'normal' commute of x miles at 8:30am and 5 miles at 5:30pm M-F
tmy['miles'] = tmy['miles'].where((tmy.index.time !=  datetime.time(8, 30))|(tmy.index.dayofweek > 4),owcommute)
tmy['miles'] = tmy['miles'].where((tmy.index.time !=  datetime.time(17, 30))|(tmy.index.dayofweek > 4),owcommute)
#that took care of times, but now for weekends, use the same times for simplicity:
tmy['miles'] = tmy['miles'].where((tmy.index.dayofweek < 5)|(tmy.index.time !=  datetime.time(8, 30)),weekend)
tmy['miles'] = tmy['miles'].where((tmy.index.dayofweek < 5)|(tmy.index.time !=  datetime.time(17, 30)),weekend)

st.write("Total yearly miles driven:", tmy['miles'].sum())

# assume an average speed to calculate how much of the hour is spent driving vs parked
speed = 30
tmy['drivetime'] = tmy['miles'] / speed  # make a new column for time spent driving in fraction of an hour

# if time is greater than an hour, we need to also mark sequential hours with correct amount

for i, t in enumerate(tmy['drivetime']):
    if t > 1:
        tmy.drivetime.iloc[i + 1] = tmy.drivetime.iloc[i + 1] + tmy.drivetime.iloc[i] - 1
        tmy.drivetime.iloc[i] = 1
tmy['parktime'] =1- tmy['drivetime']

#add a garage option for overnight parking
garage = st.checkbox("I park in a garage overnight.")
tmy['t_park'] = tmy['db_temp']  # set the default parking temp to the outside temp
if garage:
    Temp_g = st.slider('What temperature is your garage kept at in the winter?', value = 50, max_value = 80)

    # where the time is at or after 8:30 and before or at 17:30, parking temp is default, otherwise it is garage temp if garage temp < outside temp:
    tmy['t_park'] = tmy['t_park'].where(
        ((tmy.index.time >= datetime.time(8, 30)) & (tmy.index.time <= datetime.time(17, 30)))|(tmy.t_park > Temp_g), Temp_g)

# # Use the relationship between temperature and energy use to find the total energy use

#from CEA's Wattson:  to condition battery while parked: 
# parke (kWh/hr) = -.0092 * Temp(F) + .5206 (down to 2.5F at least), and not 
#less than 0!
#https://www.greencarreports.com/news/1115039_chevy-bolt-ev-electric-car-range-and-performance-in-winter-one-owners-log
#the resource above says that a Bolt used 24 miles of range when parked for 30 hours outside
#at -4F, which might be a little to a lot less than below depending on how many kWh the
#range corresponds to (temperature adjusted or not??)
#I calculate this might be anywhere from 0.2 to 0.5 kWh/hr energy use.
# The Wattson relation above gives me ~0.56kWh/hr, the code actually used below give 0.266kWh/hr

#T.S. reports 10 miles of range loss while parked for 2 hours, unplugged, at 28F (Tesla Y),
#at .28 kwh/mile, this is 1.4kWh/hr!  This is far above the range of any linear fit tried.

#Wattson relationship:
#tmy['parke'] = tmy['t_park'] * -.0092 + .5206 #linear relationship of energy use with temperature

#I have some messy data from 4 Alaskan Teslas as well, and adding to the Wattson data, here is
#the trend I get - it gives the EV a bit more benefit of the doubt!
#tmy['parke'] = tmy['t_park'] * -.005 + .341
#the most generous relationship that this data seems to allow is the code below:
#I am also working to match real yearly avg kwh/mile for a Tesla in Fairbanks (results are
# preliminary, and I will include them when the data is more complete), and it does look
#like my cold weather impacts have been a bit harsher than reality, at least for energy while parked,
#which is why I am trying to find a data-supported relationship that matches what I see in that data
tmy['parke'] = tmy['t_park'] * -.004 + .25
tmy['parke'] = tmy['parke'].where(tmy['parke'] > 0,0) #make sure this isn't less than zero!

tmy['parke'] = tmy['parke']*tmy['parktime'] #adjusted for amount of time during the hour spent parked

#if driving:
#2017 Chevy Bolt is energy per mile (epm) = 28kWh/100mi at 100% range (fueleconomy.gov)
epm = st.slider('Enter the Rated kWh/mile of the EV to investigate '
                '(this calculator internally adjusts for the effect of temperature): '
                'A 2017 Bolt is .28 according to fueleconomy.gov', value = .28, max_value = 3.0)


# if T < -9.4F, RL = .59 (probably not totally flat, but don't have data now)
#if -9.4F < T < 73.4, RL = -.007 T(F) + .524
#if 73.4 < T, RL = 0
tmy['RL'] = .59
tmy['RL'] = tmy['RL'].where((tmy['db_temp'] < -9.4), -.007*tmy['db_temp']+.524)
tmy['RL'] = tmy['RL'].where((tmy['db_temp'] < 73.4), 0)

epm_t = epm/(1-tmy['RL'])
#energy use: 
tmy['kwh']= epm_t*tmy['miles']

#add on the energy use while parked:
tmy['kwh'] = tmy.kwh + tmy.parke

#toplot=tmy['2018-5-23':'2018-5-30']
#plt.plot(toplot.index, toplot.kwh) - maybe edit to plot something with streamlit!?

#total cost to drive EV for a year:
coe = st.slider('What do you pay per kWh for electricity?', max_value = 1.0, value = .2)
st.write("Note: we do not account for PCE, block rates, or demand charges, which could make the electric costs higher than expected from this simple calculator.")
total_cost_ev = coe*tmy.kwh.sum()

#greenhouse gas emissions from electricity:
# Access Alan's Alaska utility data as a Pandas DataFrame
dfu = get_df('city-util/proc/utility.pkl')

util = dfc['ElecUtilities'].loc[dfc['aris_city']==city].iloc[0][0][1] #find a utility id for the community chosen
cpkwh_default = dfu['CO2'].loc[dfu['ID']==util].iloc[0]/2.2 #find the CO2 per kWh for the community and divide by 2.2 to change pounds to kg
cpkwh_default = float(cpkwh_default)
cpkwh = st.slider("How many kg of CO2 are emitted per kWh for your utility "
                  "(if you don't know, leave it at the default value here, which is specific to your community "
                  "but might be a couple of years out of date)?:", max_value = 2.0, value = cpkwh_default)
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
dpg = st.slider('What is the price of gas?', value = 2.5, max_value = 10.0)
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
st.write("Your personal driving habits and other real world conditions could change these results dramatically! ")
st.write("The underlying model relating energy use with temperature will be updated as we continue to collect cold weather EV data. ")
st.write("Thanks to Alan Mitchell of Analysis North for Alaskan utility data, tmy files, and wonderful code to access and use them all.")
st.write("See http://ak-energy-data.analysisnorth.com and https://github.com/alanmitchell/heat-pump-calc")
st.write("...And definitely check out the Alaskan Heat Pump Calculator at https://heatpump.cf to see if you should get a heat pump!")
st.write("")
st.write("")
st.write("Please peak under the hood at this code.  Basically, a typical year's hourly temperature profile is combined with a daily driving profile and realtionships between the energy use for driving and maintaining the EV while parked vs temperature to arrive at a cost and emissions for the kWh needed by the EV.")
st.write("email Michelle Wilber at mmwilber@alaska.edu with any suggestions or comments.")
