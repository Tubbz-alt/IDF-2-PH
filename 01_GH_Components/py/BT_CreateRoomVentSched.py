#
# IDF2PHPP: A Plugin for exporting an EnergyPlus IDF file to the Passive House Planning Package (PHPP). Created by blgdtyp, llc
# 
# This component is part of IDF2PHPP.
# 
# Copyright (c) 2020, bldgtyp, llc <info@bldgtyp.com> 
# IDF2PHPP is free software; you can redistribute it and/or modify 
# it under the terms of the GNU General Public License as published 
# by the Free Software Foundation; either version 3 of the License, 
# or (at your option) any later version. 
# 
# IDF2PHPP is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the 
# GNU General Public License for more details.
# 
# For a copy of the GNU General Public License
# see <http://www.gnu.org/licenses/>.
# 
# @license GPL-3.0+ <http://spdx.org/licenses/GPL-3.0+>
#
"""
This component is used to create a simplified PHPP-Style Ventilation Schedule for a room or zone. Input values here for time of operation and fan speed for HIGH | MED | LOW modes.
> By entering reduction factors, full or reduced ventilation operation modes within the utilisation period can be considered. All of these attributes can be manually input using the Rhino-Scene PHPP tool 'Set TFA Surface Factor(s)'.
> All times % values should add up to 100%
-
EM Feb. 25, 2020

    Args:
        _fanSpeed_high: Fan Speed factor (in %) in relation to the maximum volume flow when running at HIGH speed.
        _operationTime_high: Total operation time (in %) of HIGH SPEED ventilation mode in relation to the total. 
        _fanSpeed_med: Fan Speed factor (in %) in relation to the maximum volume flow when running at MEDIUM speed.
        _operationTime_med: Total operation time (in %) of MEDIUM SPEED ventilation mode in relation to the total.
        _fanSpeed_low: Fan Speed factor (in %) in relation to the maximum volume flow when running at LOW speed.
        _operationTime_low:Total operation time (in %) of LOW SPEED ventilation mode in relation to the total.
    Returns:
        phppVentSched_: A PHPP Room Ventilation Schedule Object. Plug into the '_phppVentSched' input on the 'Room Vent Flowrates' component.
"""

ghenv.Component.Name = "BT_CreateRoomVentSched"
ghenv.Component.NickName = "PHPP Vent Sched"
ghenv.Component.Message = 'FEB_25_2020'
ghenv.Component.IconDisplayMode = ghenv.Component.IconDisplayMode.application
ghenv.Component.Category = "BT"
ghenv.Component.SubCategory = "01 | Model"
from collections import namedtuple
import Grasshopper.Kernel as ghK

# Clean up the inputs
# Turn into decimal if >1
def cleanGet(_in, _default=None):
    try:
        result = float(_in)
        if result > 1:
            result = result / 100
        
        return result
    except:
        return _default

def checkInputs(_in):
    total = _in[0].time_high + _in[0].time_med + _in[0].time_low
    if int(total) != 1:
        mssgLostRoom = "The Operation times don't add up to 100%? Please correct the inputs."
        ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, mssgLostRoom)

# Output the cleaned results as a sched
phppSched = namedtuple('phppSched', 'speed_high time_high speed_med time_med speed_low time_low')
phppVentSched_ = [ phppSched(cleanGet(_fanSpeed_high, 1.0),
                            cleanGet(_operationTime_high, 1.0),
                            cleanGet(_fanSpeed_med, 0.77),
                            cleanGet(_operationTime_med, 0.0),
                            cleanGet(_fanSpeed_low, 0.4),
                            cleanGet(_operationTime_low, 0.0)
                            ) ]

checkInputs(phppVentSched_)

