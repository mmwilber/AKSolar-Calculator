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

st.write("This is a calculator to calculate the effective per kWh rate when the other factors are input.")

#Future update: upload a list of utilities to choose from:
#get the data
# Access as a Pandas DataFrame
#df = read_csv('rates.csv')

#now create a drop down menu of the available utilities 
#utilities = df['utility'].drop_duplicates().sort_values(ignore_index = True) #get a list of names
#utility = st.selectbox('Select a utility:', utilities ) #make a drop down list and get choice
#tmyid = dfc['TMYid'].loc[dfc['aris_city']==city].iloc[0] #find the corresponding TMYid - OLD edit this to get rate info maybe

st.write("")
st.write("Note: you may use your computer's arrow keys with the mouse to do fine adjustments to the slider values below:")

st.write("")
dc = (st.slider('Enter the demand charge, in $/kW', max_value = 44.53, value = 20.0))
ec = (st.slider('Enter the energy charge, in $/kWh', max_value = .6000, step = .0001, format = "%1.4f",value = .1200))
lf = (st.slider('Enter the assumed load factor, in %', max_value = 100.0, step = .1, format = "%1.1f",value = 10.0))

# calculate the inception rate

rate = dc/(lf/100 * 730) + ec
st.write("")
st.write("The inception rate per kWh is calculated as ", round(rate,5))
st.write("")
st.write("Note: some utilities might have seasonal rates, which may neccessitate performing more than one calculation")

st.write("")
st.write("Please peak under the hood at this code, which can be found at")
st.write("https://github.com/mmwilber/AK_EV_calculators/")
st.write("email Michelle Wilber at mmwilber@alaska.edu with any suggestions or comments.")
