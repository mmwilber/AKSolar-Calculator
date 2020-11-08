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

st.write("This is calculator to find out how much it would cost to charge an EV at home in Alaska, and what the carbon emissions would be.")
st.write("A comparison is also made to a internal combustion engine (ICE) vehicle.")
st.write("This project is still in development.")
st.write("Community and Utility data are taken from http://ak-energy-data.analysisnorth.com/ and may be a bit out of date")
st.write("Base assumptions and data will be modified as research continues!")

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


#I could also enter or assume an average speed to calculate how much 
#of the hour is spent driving vs parked, but for now, with only about 
#10-15 minutes driving, I will assume the full hour is parked + the energy
#to drive - energy use may be a little on the high side with this calc



#add a garage option for overnight parking
garage = st.checkbox("I park in a garage overnight.")
tmy['t_park'] = tmy['db_temp']  # set the default parking temp to the outside temp
if garage:
    Temp_g = st.slider('what temperature is your garage kept at in the winter?', value = 50, max_value = 80)

    # where the time is at or after 8:30 and before or at 17:30, parking temp is default, otherwise it is garage temp if gargage temp < outside temp:
    tmy['t_park'] = tmy['t_park'].where(
        ((tmy.index.time >= datetime.time(8, 30)) & (tmy.index.time <= datetime.time(17, 30)))|(tmy.t_park > Temp_g), Temp_g)

# # Use the relationship between temperature and energy use to find the total energy use

#from CEA's Wattson:  to condition battery while parked: 
# parke (kWh/hr) = -.0092 * Temp(F) + .5206 (down to 2.5F at least), and not 
#less than 0!


#https://www.greencarreports.com/news/1115039_chevy-bolt-ev-electric-car-range-and-performance-in-winter-one-owners-log
    #the resource above says that a Bolt used 24 miles of range when parked for 30 hours outside at -4F, which might be a little to a lot less than
    #below depending on how many kWh the range corresponds to (temperature adjusted or not??)
    #I calculate this might be anywhere from 0.2 to 0.5 kWh/hr energy use.  The below gives me ~0.56kWh/hr

tmy['parke'] = tmy['t_park'] * -.0092 + .5206
tmy['parke'] = tmy['parke'].where(tmy['parke'] > 0,0)

#if driving:
#2017 Chevy Bolt is energy per mile (epm) = 28kWh/100mi at 100% range (fueleconomy.gov)
epm = st.slider('enter the Rated kWh/mile of the EV to investigate, this calculator internally adjusts for the effect of temperature. A 2017 Bolt is .28 according to fueleconomy.gov', value = .28, max_value = 3.0)


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

#total cost to drive for a year:
coe = st.slider('what do you pay per kWh for electricity?', max_value = 1.0, value = .2)
total_cost_ev = coe*tmy.kwh.sum()

#comparison to gas:
mpg = st.slider('What is the mpg of your gas car?', value = 25, max_value = 60)
dpg = st.slider('what is the price of gas?', value = 2.5, max_value = 10.0)
#make this temperature dependent too like above.
#according to fueleconomy.gov, an ICE can have 15 to 25% lower mpg at 20F than 77F. the 25% is for trips under 3-4 miles, so could adjust the below later for this
#for now I am just using 20% less
tmy['mpg'] = mpg
tmy['mpg'] = tmy['mpg'].where((tmy['db_temp'] > 77), mpg - .2*mpg*(77-tmy['db_temp'])/57)

tmy['gas'] = tmy.miles/tmy.mpg
total_cost_gas = tmy.gas.sum()*dpg

#what about the engine block heater?  Say 120 days (really less),
#plugged in for 2 hours a day:
kwh_block = .4*2*120
cost_block = .2*kwh_block
if garage:
    cost_block = 0

#now look at ghg emissions:
#Every gallon of gasoline burned creates about 8.887 kg of CO2 (EPA)
ghg_ice = 8.887*tmy.gas.sum()

#from R Dones et al Greenhouse Gas Emissions from Energy Systems: Comparison and Overview 
#table 2 and text
#the best combined cycle gas plants emit .420kg/kWh, avg more like .5
#hydro = .003 to .03 kg/kWh
#wind = .01 - .02
#PV = .079
#CEA website: in 2016 86%gas, 11%hydro, 3%wind
#cea_pkwh = .86*.5 + .11*.03 + .3*.02
#update the above with sliders for coal, gas, hydro, etc maybe?  Or choose your utility (cost too)

# Access Alan's Alaska utility data as a Pandas DataFrame
dfu = get_df('city-util/proc/utility.pkl')

util = dfc['ElecUtilities'].loc[dfc['aris_city']==city].iloc[0][0][1] #find a utility id for the community chosen
cpkwh = dfu['CO2'].loc[dfu['ID']==util].iloc[0]/2.2 #find the CO2 per kWh for the community and divide by 2.2 to change pounds to kg
st.write("kg of CO2 per kWh for utility:", round(cpkwh,3))
st.write("utility ID", util)
st.write(city)
ghg_ev = cpkwh*tmy.kwh.sum()

ghg_block = cpkwh*kwh_block
if garage:
    ghg_block = 0

st.write("")
st.write("Total cost of EV fuel = $", round(total_cost_ev,2))
st.write("Total cost of ICE fuel = $", round(total_cost_gas+cost_block,2))
st.write("Total kg CO2 EV = ", round(ghg_ev,2))
st.write("Total kg CO2 ICE = ", round(ghg_ice + ghg_block,2))
st.write(" ")
st.write("Your personal driving habits and other real world conditions could change these results dramatically! ")
st.write("Also, the underlying assumptions will be updated as we get better data. ")




