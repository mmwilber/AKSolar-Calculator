import os
import io
import math
import functools
#import urllib
import datetime
import streamlit as st
import pandas as pd
import numpy as np
#import requests

#import matplotlib.pyplot as plt

st.image(['ACEP.png'])
st.title("Alaska Electric Vehicle Charging Inception Rate Calculator")
st.write("")
st.write("In October 2021, the Regulatory Commission or Alaska issued U-21-022(2), \
an order granting, in part, a petition for approval of a 2-part rate \
for electric vehicle charging stations where the new rate is determined by the formula: ")
st.write("[Demand Charge/(Assumed LF x 730)] + Energy Charge,") 
st.write("where each utility would use the \
current demand and energy charges approved in its last general rate case and propose and \
support an assumed load factor as part of its tariff filing proposing a DCFC inception rate for RCA approval.")

st.write("This is a calculator to calculate the effective per kWh inception rate, given an assumed load factor.")

#upload a list of utilities to choose from:
#upload the csv of rates
# 
df = pd.DataFrame()
df = pd.read_csv('utility_rates_12_8_21.csv')
st.write("Rates in our database are valid on 12/8/21")
one = st.checkbox("Check here if you want to look at a specific utility's inception rate, otherwise all the utilities on file will be compared.")
if one:
  
  #now create a drop down menu of the available utilities 
  utilities = df['Utility'] #get a list of names
  utility = st.selectbox('Select a utility:', utilities ) #make a drop down list and get choice


  custom = st.checkbox("Check here if your utility wasn't listed or you would like to use custom or updated rate")

  st.write("")
  if custom:
  
    st.write("Note: you may use your computer's arrow keys with the mouse to do fine adjustments to the slider values below:")

    st.write("")
    dc = (st.slider('Enter the demand charge, in $/kW', max_value = 44.53, value = 20.0))
    ec = (st.slider('Enter the energy charge, in $/kWh', max_value = .6000, step = .0001, format = "%1.4f",value = .1200))
  
  else:
    dc = df['LCD'].loc[df['Utility']==utility].iloc[0] #find the corresponding demand rate
    ec = df['LCE'].loc[df['Utility']==utility].iloc[0] #find the corresponding energy rate
  
  lf = (st.slider('Enter the assumed load factor, in %', max_value = 100.0, step = .1, format = "%1.1f",value = 10.0))

  # calculate the inception rate

  rate = dc/(lf/100 * 730) + ec
  st.write("")
  st.write("The inception rate per kWh is calculated as ", round(rate,5))
  st.write("")
  st.write("Note: some utilities might have seasonal rates, which may neccessitate performing more than one calculation")

else:
  lf = (st.slider('Enter the assumed load factor, in %', max_value = 100.0, step = .1, format = "%1.1f",value = 10.0))
  df['IR'] = df['LCD']/(lf/100 * 730) + df['LCE']
  tab = df[['Utility']]
  tab['Inception Rate'] = df.IR
  tab['Small Commercial Rate'] = df.SCE
  tab = tab.set_index('Utility')
  st.table(tab)


st.write("")
st.write("Please peak under the hood at this code, which can be found at")
st.write("https://github.com/mmwilber/AK_EV_calculators/")
st.write("email Michelle Wilber at mmwilber@alaska.edu with any suggestions or comments.")
