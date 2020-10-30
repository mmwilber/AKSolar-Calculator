#!/usr/bin/env python
# coding: utf-8
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

# There is a file with summary info about each site 
# available.
df = get_df('wx/tmy3/proc/tmy3_meta.pkl')
df.head()

#get the tmy for Anchorage
tmy = tmy_from_id(702730)
#note: the temperatures are in F :)

st.write("This is calculator to find out how much it would cost to charge an EV at home in Anchorage, Alaska, and what the carbon emissions would be.")
st.write("It assumes that the only driving is to and from work Monday through Friday, and that the vehicle is always parked outside")
st.write("A comparison is also made to a internal combustion engine (ICE) vehicle.")
st.write("This project is still in development and other communities in Alaska will be added.")
st.write("Base assumptions and data will be modified as research continues!")

# # put together a driving profile

owcommute = st.slider('How many miles do you live from work?', value = 5)
tmy['miles'] = 0
#I'm going to put in a 'normal' commute of x miles at 8:30am and 5 miles at 5:30pm M-F
tmy['miles'] = tmy['miles'].where((tmy.index.time !=  datetime.time(8, 30)),owcommute)
tmy['miles'] = tmy['miles'].where((tmy.index.time !=  datetime.time(17, 30)),owcommute)
#that took care of times, but now correct for weekends:
tmy['miles'] = tmy['miles'].where((tmy.index.dayofweek < 5),0)


#I could also enter or assume an average speed to calculate how much 
#of the hour is spent driving vs parked, but for now, with only about 
#10-15 minutes driving, I will assume the full hour is parked + the energy
#to drive - energy use may be a little on the high side with this calc


# # Use the relationship between temperature and energy use to find the total energy use

#from CEA's Wattson:  to condition battery while parked: 
# parke (kWh/hr) = -.0092 * Temp(F) + .5206 (down to 2.5F at least), and not 
#less than 0!
tmy['parke'] = tmy['db_temp'] * -.0092 + .5206
tmy['parke'] = tmy['parke'].where(tmy['parke'] > 0,0)
#tmy['parke'] = tmy['parke'].where(tmy['parke'] < .06,.06) #this is for storage in 50F garage - take out if parked outside

#if driving:
#2017 Chevy Bolt is energy per mile (epm) = 28kWh/100mi at 100% range (fueleconomy.gov)
epm = st.slider('enter the kWh/mile of the EV to investigate. A 2017 Bolt is .28 according to fueleconomy.gov', value = .28, max_value = 3.0)
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
#plt.plot(toplot.index, toplot.kwh) - maybe edit to plot with streamlit!

#total cost to drive for a year:
coe = st.slider('what do you pay per kWh for electricity?', max_value = 1.0, value = .2)
total_cost_ev = coe*tmy.sum()[7]

#the part just from driving:
#(tmy.sum()[7]-tmy.sum()[5])*coe

#comparison to gas:
mpg = st.slider('What is the mpg of your gas car?', value = 25, max_value = 60)
dpg = st.slider('what is the price of gas?', value = 2.5, max_value = 10.0)
gas_g = tmy.sum()[4]/mpg
total_cost_gas = gas_g*dpg

#what about the engine block heater?  Say 120 days (really less),
#plugged in for 2 hours a day:
kwh_block = .4*2*120
cost_block = .2*kwh_block

#now look at ghg emissions:
#Every gallon of gasoline burned creates about 8.887 kg of CO2 (EPA)
ghg_ice = 8.887*gas_g

#from R Dones et al Greenhouse Gas Emissions from Energy Systems: Comparison and Overview 
#table 2 and text
#the best combined cycle gas plants emit .420kg/kWh, avg more like .5
#hydro = .003 to .03 kg/kWh
#wind = .01 - .02
#PV = .079
#CEA website: in 2016 86%gas, 11%hydro, 3%wind
cea_pkwh = .86*.5 + .11*.03 + .3*.02
#update the above with sliders for coal, gas, hydro, etc maybe?  Or choose your utility (cost too)

ghg_ev = cea_pkwh*tmy.sum()[7]

ghg_block = cea_pkwh*kwh_block


st.write("Total cost of EV fuel = $", round(total_cost_ev,2))
st.write("Total cost of ICE fuel = $", round(total_cost_gas+cost_block,2))
st.write("Total kg CO2 EV = ", round(ghg_ev,2))
st.write("Total kg CO2 ICE = ", round(ghg_ice + ghg_block,2))





