#This is based on the EV_Emissions.py calculator, using Tok bus energy use vs. temperature data.  No parked energy use data exists currently
#assume 30mph and subtract off travel time from parked time.
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
st.image(['ACEP.png'])
st.title("Alaska Electric School Bus Calculator")
st.write("")
st.write("This is a calculator to find out how much it would cost to charge an E-bus in Alaska, and what the carbon emissions would be.")
st.write("A comparison is also made to an internal combustion engine (ICE) Bus.")
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
beg = st.date_input('Enter the first day of summer break?', datetime.date(2018,5,23))
end = st.date_input('Enter the first day of the school year?', datetime.date(2018,8,23))

#if end before beg, switch them.  Will have to force year to be 2018 if that is not chosen

owcommute = (st.slider('How many total miles are driven each weekday during the school year', value = 10))/2
weekend = (st.slider('How many miles are driven on a weekend day during the school year?', value = 0))/2
summer_week = (st.slider('How many total miles are driven each weekday during the summer', value = 10))/2
summer_weekend = (st.slider('How many miles are driven on a weekend day during the summer?', value = 0))/2
tmy['miles'] = 0
#Assume x miles at 8:30am and x miles at 3:30pm M-F
summer = tmy[beg:end]
winter = pd.concat([tmy['2018-1-1':beg],tmy[end:'2018-12-31']])
#Assume x miles at 8:30am and x miles at 3:30pm M-F during the school year
## SCHOOL YEAR ONLY  
winter['miles'] = winter['miles'].where((winter.index.time !=  datetime.time(8, 30))|(winter.index.dayofweek > 4),owcommute)
winter['miles'] = winter['miles'].where((winter.index.time !=  datetime.time(15, 30))|(winter.index.dayofweek > 4),owcommute)

#now for weekends, use the same times for simplicity:
winter['miles'] = winter['miles'].where((winter.index.dayofweek < 5)|(winter.index.time !=  datetime.time(8, 30)),weekend)
winter['miles'] = winter['miles'].where((winter.index.dayofweek < 5)|(winter.index.time !=  datetime.time(15, 30)),weekend)


#now for summer:
summer['miles'] = summer['miles'].where((summer.index.time !=  datetime.time(8, 30))|(summer.index.dayofweek > 4),summer_week)
summer['miles'] = summer['miles'].where((summer.index.time !=  datetime.time(15, 30))|(summer.index.dayofweek > 4),summer_week)
#now for summer weekends, use the same times for simplicity:
summer['miles'] = summer['miles'].where((summer.index.dayofweek < 5)|(summer.index.time !=  datetime.time(8, 30)),summer_weekend)
summer['miles'] = summer['miles'].where((summer.index.dayofweek < 5)|(summer.index.time !=  datetime.time(15, 30)),summer_weekend)

tmy = pd.concat([winter,summer], sort = True)

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
garage = st.checkbox("The bus is parked in a garage when not driven.")
tmy['t_park'] = tmy['db_temp']  # set the default parking temp to the outside temp
if garage:
    Temp_g = st.slider('What temperature is your garage kept at in the winter?', value = 50, max_value = 80)

    # set parking temp to garage temp if garage temp < outside temp:
    tmy['t_park'] = tmy['t_park'].where((tmy.t_park > Temp_g), Temp_g) #pandas where replaces values where condition is false.

# # Use the relationship between temperature and energy use to find the total energy use

#from CEA's Wattson:  to condition battery while parked: 
# parke (kWh/hr) = -.0092 * Temp(F) + .5206 (down to 2.5F at least), and not 
#less than 0!

#EVs use energy while parked to condition the battery or precondition the battery and vehicle.  I do not have bus specific data.
#for now I am using passenger car data, which is likely quite low as the batteries are smaller.  I will update this when I can.
#Wattson (CEA Chevy Bolt) relationship:
tmy['parke'] = tmy['t_park'] * -.0092 + .5206 #linear relationship of energy use with temperature
tmy['parke'] = tmy['parke'].where(tmy['parke'] > 0,0) #make sure this isn't less than zero!

tmy['parke'] = tmy['parke']*tmy['parktime'] #adjusted for amount of time during the hour spent parked

st.write("") #some spaces to try to keep text from overlapping
#if driving:

#Based on data from winter 2020-2021 this is the best fit equation for energy use vs temperature for the Tok school bus:
# energy per mile as a function of T: epm_t (kWh/mile) = -0.034 * Temp(C) + 2.092

epm_t = -.034 *(5/9)*(tmy['db_temp'] - 32)+2.092
#energy use: 
tmy['kwh']= epm_t*tmy['miles']

#add on the energy use while parked:
tmy['kwh'] = tmy.kwh + tmy.parke

#toplot=tmy['2018-5-23':'2018-5-30']
#plt.plot(toplot.index, toplot.kwh) - maybe edit to plot something with streamlit!?

#total cost to drive EV for a year:
coe = st.slider('What is the per kWh cost for electricity?', max_value = 1.0, value = .14)
demand = st.slider('What is the demand cost per kW?', max_value = 45.0, value = 22.0)
st.write("For example, in Nov. 2021, AEL&P in Juneau had a per kWh commercial EV rate of $0.064 with no demand charge")
st.write("CEA South in Anchorage had a large commercial rate of $0.1145/kWh with a demand charge of $21.98/kW")
st.write("Note: some utilities might have seasonal or block rates, which we do not account for in this simple calculator.")
st.write("We are also leaving out the meter/customer monthly charge.")

charger_power = st.slider('What is the power of your Charger?', max_value = 350.0, value = 7.0)
total_cost_ev = coe*tmy.kwh.sum() + 12*demand*charger_power

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
ispv = st.checkbox("I will have solar panels for the purpose of offsetting EV emissions.")
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
mpg = st.slider('What is the mpg of your diesel bus?', value = 10, max_value = 30)
dpg = st.slider('What is the price of diesel per gallon?', value = 3.5, max_value = 10.0)
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

#plug = st.checkbox("I have a block heater on my gas car.")  #can add this back if find out buses ever have block heaters, etc!

#if plug:
#    st.write("This calculator assumes a block heater is used for your gas car any day the minimum temperature has been less than 20F")
#    plug_hrs = st.slider("How many hours do you plug in your block heater each day?", max_value = 24, value = 2)
#    plug_w = st.slider("How many watts is your block heater (or block plus oil heater)?", min_value = 400, max_value = 1600)
#    kwh_block = plug_w/1000*plug_hrs*plug_days
#else:
#    kwh_block = 0
kwh_block = 0 # delete this line if add back the above
cost_block = coe*kwh_block
idle = st.slider("How many minutes do you idle the diesel bus on cold days (to warm up or keep warm)?", max_value = 500, value = 5)
idleg = .2*idle/60*plug_days #cars use about .2g/hr or more at idle : https://www.chicagotribune.com/autos/sc-auto-motormouth-0308-story.html
#change above as needed for buses!

total_cost_gas = (tmy.gas.sum()+idleg)*dpg

#now look at ghg emissions:
#Every gallon of diesel burned creates about 10.180 kg of CO2 (EPA https://www.epa.gov/greenvehicles/greenhouse-gas-emissions-typical-passenger-vehicle)
ghg_ice = 10.180*(tmy.gas.sum()+idleg)

ghg_ev = cpkwh*(tmy.kwh.sum() - pvkwh)
if ghg_ev < 0:
    ghg_ev = 0

ghg_block = cpkwh*kwh_block

st.write("")
st.write("The effective yearly average kWh/mile for an electric Bus is calculated as ", round(tmy.kwh.sum()/tmy.miles.sum(),2))
st.write("This is lower than the rated kWh/mile - cold temperatures lower the range and driving efficiency, and also lead to energy use to keep the battery warm while parked. ")
st.write("")
st.write("Total cost of EV fuel per year = $", round(total_cost_ev,2))
st.write("Total cost of ICE fuel per year = $", round(total_cost_gas+cost_block,2))
st.write("Total kg CO2 EV per year = ", round(ghg_ev,2))
st.write("Total kg CO2 ICE per year = ", round(ghg_ice + ghg_block,2))
st.write(" ")
st.write("These results are preliminary and subject to change with more data!!")
st.write("The calculations are based on energy use vs. temperature data for the Tok electric School bus from the first winter of driving, results are preliminary. ")
st.write("Driving habits and other real world conditions could change these results dramatically! ")
st.write("The underlying model relating energy use with temperature will be updated as we continue to collect cold weather EV data. ")
st.write("Thanks to Stretch Blackard of Tok Transportation for graciously sharing data.")
st.write("Thanks to Alan Mitchell of Analysis North for Alaskan utility data, tmy files, and wonderful code to access and use them all.")
st.write("See http://ak-energy-data.analysisnorth.com and https://github.com/alanmitchell/heat-pump-calc")
st.write("...And definitely check out the Alaskan Heat Pump Calculator at https://heatpump.cf to see if you should get a heat pump!")
st.write("")
st.write("")
st.write("Please peak under the hood at this code.  Basically, a typical year's hourly temperature profile is combined with a daily driving profile and realtionships between the energy use for driving and maintaining the EV while parked vs temperature to arrive at a cost and emissions for the kWh needed by the EV.")
st.write("https://github.com/mmwilber/AK_EV_calculators/")
st.write("email Michelle Wilber at mmwilber@alaska.edu with any suggestions or comments.")
