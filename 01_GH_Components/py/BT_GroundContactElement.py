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
Create a ground contact 'Floor Element' for use in writing to the 'Ground' worksheet. By Default, this will just create a single floor element. You can input up to 3 of these (as a flattened list) into the 'grndFloorElements_' input on the 'Create Excel Obj - Geom' component. 
However, if you also pass in the Honeybee Zones (into _HBZones) this will try and sort out the right ground element from the HB Geometry and parameters for each zone input. This info will be automatcally passed through to the Excel writer. If you have a simple situation, you can pass all of the Honeybee zones in at once, but if you need to set detailed parameters for multiple different floor types, first explode the Honeybee Zone object and then apply one of these components to each zone one at a time. Merge the zones back together before passing along.
-
EM August 16, 2020
    Args:
        _HBZones: (list) <Optional> The Honeybee Zone Objects. 
        _type: (string): Input a floor element 'type'. Choose either:
            > 01_SlabOnGrade
            > 02_HeatedBasement
            > 03_UnheatedBasement
            > 04_SuspendedFloorOverCrawlspace
        _floorSurfaces: (List) Rhino Surface objects which describe the ground-contact surface. If the surfaces have a U-Value assigned that will be read to create the object. Use the 'Set Surface Params' tool in Rhino to set parameters for the surface before inputing.
        _exposedPerimCrvs: (List) Rhino Curve object(s) [or Surfaces] which describe the 'Exposed' perimeter of the ground contact surface(s). If these curves have a Psi-Value assigned that will be read and used to create the object. Use the 'Linear Thermal Bridge' tool in Rhino to assign Psi-Values to curves before inputing. If a surface is passed in, will use the total perimeter length of the surface as 'exposed' and apply a default Psi-Value of 0.5 W/mk for all edges.
    Returns:
        floorElement_: A single 'Floor Element' object. Input this into the 'grndFloorElements_' input on the 'Create Excel Obj - Geom' component to write to PHPP.
        HBZones_: The Honeybee zone Breps to pass along to the next component
"""

ghenv.Component.Name = "BT_GroundContactElement"
ghenv.Component.NickName = "Create Floor Element"
ghenv.Component.Message = 'AUG_16_2020'
ghenv.Component.IconDisplayMode = ghenv.Component.IconDisplayMode.application
ghenv.Component.Category = "BT"
ghenv.Component.SubCategory = "01 | Model"

import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs
from contextlib import contextmanager
import ghpythonlib.components as ghc
import Grasshopper.Kernel as ghK
import json
import re

# Classes and Defs
preview = sc.sticky['Preview']
PHPP_grnd_FloorElement = sc.sticky['PHPP_grnd_FloorElement']
PHPP_grnd_SlabOnGrade = sc.sticky['PHPP_grnd_SlabOnGrade']
PHPP_grnd_HeatedBasement = sc.sticky['PHPP_grnd_HeatedBasement']
PHPP_grnd_UnheatedBasement= sc.sticky['PHPP_grnd_UnheatedBasement']
PHPP_grnd_SuspendedFloor = sc.sticky['PHPP_grnd_SuspendedFloor']
hb_hive = sc.sticky["honeybee_Hive"]()
HBZoneObjects = hb_hive.callFromHoneybeeHive(_HBZones)

def convertUnits(_inputString, _outputUnit):
    schema = {
                'M':{'SI': 1, 'M':1, 'CM':0.01, 'MM':0.001, 'FT':0.3048, "'":0.3048, 'IN':0.0254, '"':0.0254},
                'W/M2K':{'SI':1, 'IP':5.678264134},
                'W/MK':{'SI':1, 'IP':1.730734908},
                'M3':{'SI':1, 'FT3':0.028316847},
              }
    
    inputValue = _inputString
    
    try:
        # Pull out just the decimal numeric characters, if any
        for each in re.split(r'[^\d\.]', _inputString):
            if len(each)>0:
                inputValue = each
                break # will only take the first number found, 'ft3' doesn't work otherwise
        
        inputUnit = findInputStringUnit(_inputString)
        conversionFactor = schema.get(_outputUnit, {}).get(inputUnit, 1)
        return float(inputValue) * float(conversionFactor)
    except:
        return inputValue

def findInputStringUnit(_in):
    evalString = str(_in).upper()
    
    if 'FT' in evalString or "'" in evalString:
        inputUnit = 'FT'
    elif 'IN' in evalString or '"' in evalString:
        inputUnit = 'IN'
    elif 'MM' in evalString:
        inputUnit = 'MM'
    elif 'CM' in evalString:
        inputUnit = 'CM'
    elif 'M' in evalString and 'MM' not in evalString:
        inputUnit = 'M'
    elif 'IP' in evalString:
        inputUnit = 'IP'
    elif 'FT3' in evalString:
        inputUnit = 'FT3'
    else:
        inputUnit = 'SI'
    
    return inputUnit

def cleanInputs(_in, _nm, _default, _units=None):
    # Apply defaults if the inputs are Nones
    out = _in if _in != None else _default
    out = convertUnits(str(out), _units)
    
    # Check that output can be float
    try:
        # Check units
        if _nm == "thickness":
            if float(out.ToString()) > 1:
                unitWarning = "Check thickness units? Should be in METERS not MM." 
                ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, unitWarning)
            return float(out.ToString())
        elif _nm == 'orientation':
            return out
        elif _nm == 'psi':
            return str(out)
        else:
            return float(out.ToString())
    except:
        ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Error, '"{}" input should be a number'.format(_nm))
        return out

def setupInputs(_type):
    
    direction = 'Please input a valid Floor Type into "_type". Input either:\n'\
    '    1: Slab on Grade\n'\
    '    2: Heated Basement\n'\
    '    3: UnHeated Basement\n'\
    '    4: Suspeneded Floor over Crawspace'
    
    # Setup Inputs based on type
    inputs_slabOnGrade = {
        4:{'name':'_exposedPerimPsiValue', 'desc':'(float) Psi-Value of the perimeter slab-edge thermal bridge (w/mk). Default is None (0)'},
        5:{'name':'_perimInsulWidthOrDepth', 'desc':'(float) The width or depth (m) beyond the face of the building enclosure which the perimeter insualtion extends. For vertical, measure this length from the underside of the floor slab insulation. Default is 1 m.'},
        6:{'name':'_perimInsulThickness', 'desc':'(float) Perimeter Insualtion Thickness (m). Default is 0.101 m'},
        7:{'name':'_perimInsulConductivity', 'desc':'(float) Perimeter Insulation Thermal Conductivity (W/mk). Default is 0.04 W/m2k'},
        8:{'name':'_perimInsulOrientation', 'desc':'(string) Perimeter Insulation Orientation. Input either "Vertical" or "Horizontal". Default is "Vertical".'}
        }
    
    inputs_heatedBasement = {
        4:{'name':'_exposedPerimPsiValue', 'desc':'(float) Psi-Value of the perimeter slab-edge thermal bridge (w/mk). Default is None (0)'},
        7:{'name':'_wallBelowGrade_height', 'desc':'(float) Average height (m) from grade down to base of basement wall.'},
        8:{'name':'_wallBelowGrade_Uvalue', 'desc':'(float) U-Value (W/m2k) of wall below grade.'},
        }
    
    inputs_unheatedBasement =  {  
        4:{'name':'_exposedPerimPsiValue', 'desc':'(float) Psi-Value of the perimeter slab-edge thermal bridge (w/mk). Default is None (0)'},
        5:{'name':'_wallAboveGrade_height', 'desc':'(float) Average height (m) from grade up to top of  basement wall.'},
        6:{'name':'_wallAboveGrade_Uvalue', 'desc':'(float) U-Value (W/m2k) of wall above grade.'},
        7:{'name':'_wallBelowGrade_height', 'desc':'(float) Average height (m) from grade down to base of basement wall.'},
        8:{'name':'_wallBelowGrade_Uvalue', 'desc':'(float) U-Value (W/m2k) of wall below grade.'},
        9:{'name':'_basementFloor_Uvalue', 'desc':'(float) U-Value (W/m2k) of the basement floor slab.'},
        10:{'name':'_basementAirChange', 'desc':'(float) Air exchange rate (ACH) in the unheated basement. A Typical value is 0.2ACH'},
        11:{'name':'_basementVolume', 'desc':'(float) Air Volume (m3) of the unheated basement. The basement ventilation heat losses are calculated based on this volume and the air exchange.'}
        }
        
    inputs_suspendedFloor =  {  
        4:{'name':'_exposedPerimPsiValue', 'desc':'(float) Psi-Value of the perimeter slab-edge thermal bridge (w/mk). Default is None (0)'},
        5:{'name':'_wallCrawlSpace_height', 'desc':'(float) Average height (m) of the crawl space walls.'},
        6:{'name':'_wallCrawlSpace_Uvalue', 'desc':'(float) U-Value (W/m2k) of the crawl space walls.'},
        7:{'name':'_crawlSpace_UValue', 'desc':'(float) U-Value of the floor under the crawl space. If the ground is not insulated, the heat transfer coefficient of 5.9 W/m2k must be used.'},
        8:{'name':'_ventilationOpeningArea', 'desc':'(float) Total area (m2) of the ventilation openings of the crawl space.'},
        9:{'name':'_windVelocityAt10m', 'desc':'(float) Average wind velocity (m/s) at 10m height in the selected location. Default is 4 m/s.'},
        10:{'name':'_windShieldFactor', 'desc':'(float) Wind Shield Factor. Default is 0.05. Typical Values:\n-Protected Site (city center): 0.02\n-Average Site (suburb): 0.05\n-Exposed Site (rural):0.10'}
        }
    
    if _type == None:
        inputs = {}
        ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, direction)
    else:
        if '1' in str(_type):
            inputs = inputs_slabOnGrade
        elif '2' in str(_type):
            inputs = inputs_heatedBasement
        elif '3' in str(_type):
            inputs = inputs_unheatedBasement
        elif '4' in str(_type):
            inputs = inputs_suspendedFloor
        else:
            inputs = {}
            ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, direction)
            
    for inputNum in range(4, 12):
        item = inputs.get(inputNum, {'name':'-', 'desc':'-'})
        
        ghenv.Component.Params.Input[inputNum].NickName = item.get('name')
        ghenv.Component.Params.Input[inputNum].Name = item.get('name')
        ghenv.Component.Params.Input[inputNum].Description = item.get('desc')
        
    return inputs

def updateHBFloorElement(_flag, _floorSurfaces, floorElement_, _zone, _flrType):
    if _flag==True and len(_floorSurfaces)==0:
        floorElement_.getParamsFromRH(_zone, _flrType)
        setattr(_zone, 'PHPP_ground', floorElement_)
    else:
        if len(_floorSurfaces)>0:
            setattr(_zone, 'PHPP_ground', floorElement_)
        else:
            setattr(_zone, 'PHPP_ground', None)

#-------------------------------------------------------------------------------
# For some damn reason, have to instantiate these before run. 
# Must be a way to automate this but can't figure out right now so 
# doing it manually. 
_exposedPerimPsiValue = None
_perimInsulWidthOrDepth = None
_perimInsulThickness = None
_perimInsulConductivity = None
_perimInsulOrientation = None
_wallBelowGrade_height = None
_wallBelowGrade_Uvalue = None
_wallAboveGrade_height = None
_wallAboveGrade_Uvalue = None
_basementFloor_Uvalue = None
_basementAirChange = None
_basementVolume = None
_wallCrawlSpace_height = None
_wallCrawlSpace_Uvalue = None
_crawlSpace_UValue = None
_ventilationOpeningArea = None
_windVelocityAt10m = None
_windShieldFactor = None

inputNames = setupInputs(_type)
ghenv.Component.Attributes.Owner.OnPingDocument()

if _type == None:
    _type = ''

#-------------------------------------------------------------------------------
if '1' in str(_type):
    # Set the input data Explicitly
    for input in ghenv.Component.Params.Input:
        if input.Name == '_exposedPerimPsiValue':
            for each in input.VolatileData.AllData(True):
                _exposedPerimPsiValue = each
        elif input.Name == '_perimInsulWidthOrDepth':
            for each in input.VolatileData.AllData(True):
                _perimInsulWidthOrDepth = each
        elif input.Name == '_perimInsulThickness':
            for each in input.VolatileData.AllData(True):
                _perimInsulThickness = each
        elif input.Name == '_perimInsulConductivity':
            for each in input.VolatileData.AllData(True):
                _perimInsulConductivity = each
        elif input.Name == '_perimInsulOrientation':
            for each in input.VolatileData.AllData(True):
                _perimInsulOrientation = each
    
    # Get user inputs, set defaults
    perimPsi = cleanInputs(_exposedPerimPsiValue, 'psi', None, 'W/MK')
    depth = cleanInputs(_perimInsulWidthOrDepth, "depth", 1.0, 'M')
    thickness = cleanInputs(_perimInsulThickness, "thickness", 0.101, 'M')
    conductivity = cleanInputs(_perimInsulConductivity, "lambda", 0.04, 'W/MK')
    orientation = cleanInputs(_perimInsulOrientation, "orientation", 'Vertical')
    
    # Sort out Perim Curve Inputs
    perimCrvs = []
    for i, crv in enumerate(_exposedPerimCrvs):
        try:
            perimCrvs.append( float(crv) )
        except:
            try:
                rhinoGuid = ghenv.Component.Params.Input[3].VolatileData[0][i].ReferenceID.ToString()
                perimCrvs.append( rhinoGuid )
            except:
                warning = 'Please input only curves, surfaces or numbers (list) for _exposedPerimCrvs'
                ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, warning)
    
    # Build Floor Elements for any HB Zones input
    # See if any of the Zones include at least one SlabOnGrade surface?
    anyZoneincludesSlabOnGrade = False
    for zone in HBZoneObjects:
        thisZoneincludesSlabOnGrade = False
        for srfc in zone.surfaces:
            if srfc.srfType[srfc.type] == 'SlabOnGrade':
                anyZoneincludesSlabOnGrade = True
                thisZoneincludesSlabOnGrade = True
                break
        
        # Create a new Floor Element & Update the with the HB Zone Params
        floorElement_ = PHPP_grnd_SlabOnGrade( zone.name, _floorSurfaces, perimCrvs, perimPsi, depth, thickness, conductivity, orientation)
        updateHBFloorElement(thisZoneincludesSlabOnGrade, _floorSurfaces, floorElement_, zone, 'SlabOnGrade')
        
        for warning in floorElement_.getWarnings():
            ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, warning)
    
    if anyZoneincludesSlabOnGrade == False:
        msg = "I could not find any 'SlabOnGrade' elements in any of the HB zones input? Are you sure\n"\
        "this is the right type of foundation? For now I will use the parameter values\n"\
        "input here, but maybe double check your Rhino surface assignments?"
        ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Remark, msg)
    
#-------------------------------------------------------------------------------
elif '2' in str(_type):
    # Set the input data Explicitly
    for input in ghenv.Component.Params.Input:
        if input.Name == '_exposedPerimPsiValue':
            for each in input.VolatileData.AllData(True):
                _exposedPerimPsiValue = each
        elif input.Name == '_wallBelowGrade_height':
            for each in input.VolatileData.AllData(True):
                _wallBelowGrade_height = each
        elif input.Name == '_wallBelowGrade_Uvalue':
            for each in input.VolatileData.AllData(True):
                _wallBelowGrade_Uvalue = each
    
    # Clean the Inputs and check formats, types
    perimPsi = cleanInputs(_exposedPerimPsiValue, 'psi', None, 'W/MK')
    wallHeight_BG = cleanInputs(_wallBelowGrade_height, "height_bg", 1.0, 'M')
    wallU_BG = cleanInputs(_wallBelowGrade_Uvalue, "Uvalue_bg", 1.0, 'W/M2K')
    
    # Sort out Perim Curve Inputs
    perimCrvs = []
    for i, crv in enumerate(_exposedPerimCrvs):
        try:
            perimCrvs.append( float(crv) )
        except:
            try:
                rhinoGuid = ghenv.Component.Params.Input[3].VolatileData[0][i].ReferenceID.ToString()
                perimCrvs.append( rhinoGuid )
            except:
                warning = 'Please input only curves, surfaces or numbers (list) for _exposedPerimCrvs'
                ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, warning)
    
    # See if any of the Zone includes at least one UndergroundSlab surface?
    anyZoneincludesUndergroundSlab = False
    for zone in HBZoneObjects:
        thisZoneincludesUndergroundSlab = False
        for srfc in zone.surfaces:
            if srfc.srfType[srfc.type] == 'UndergroundSlab':
                anyZoneincludesUndergroundSlab = True
                thisZoneincludesUndergroundSlab = True
                break
                
        # Create a new Floor Element & Update the with the HB Zone Params
        floorElement_ = PHPP_grnd_HeatedBasement( zone.name, _floorSurfaces,  perimCrvs, perimPsi, wallHeight_BG, wallU_BG )
        updateHBFloorElement(thisZoneincludesUndergroundSlab, _floorSurfaces, floorElement_, zone, 'UndergroundSlab')
        
        for warning in floorElement_.getWarnings():
            ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, warning)
    
    if anyZoneincludesUndergroundSlab == False:
        msg = "I could not find any 'UndergroundSlab' elements in any of the HB zones input? Are you sure\n"\
        "this is the right type of foundation? For now I will use the parameter values\n"\
        "input here, but maybe double check your Rhino surface assignments?"
        ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Remark, msg)

    
#-------------------------------------------------------------------------------
elif '3' in str(_type):
    # Set the input data Explicitly
    for input in ghenv.Component.Params.Input:
        if input.Name == '_exposedPerimPsiValue':
            for each in input.VolatileData.AllData(True):
                _exposedPerimPsiValue = each
        elif input.Name == '_wallAboveGrade_height':
            for each in input.VolatileData.AllData(True):
                _wallAboveGrade_height = each
        elif input.Name == '_wallAboveGrade_Uvalue':
            for each in input.VolatileData.AllData(True):
                _wallAboveGrade_Uvalue = each
        elif input.Name == '_wallBelowGrade_height':
            for each in input.VolatileData.AllData(True):
                _wallBelowGrade_height = each
        elif input.Name == '_wallBelowGrade_Uvalue':
            for each in input.VolatileData.AllData(True):
                _wallBelowGrade_Uvalue = each
        elif input.Name == '_basementFloor_Uvalue':
            for each in input.VolatileData.AllData(True):
                _basementFloor_Uvalue = each
        elif input.Name == '_basementAirChange':
            for each in input.VolatileData.AllData(True):
                _basementAirChange = each
        elif input.Name == '_basementVolume':
            for each in input.VolatileData.AllData(True):
                _basementVolume = each
    
    # Clean User Inputs
    perimPsi = cleanInputs(_exposedPerimPsiValue, 'psi', None, 'W/MK')
    wallHeight_AG = cleanInputs(_wallAboveGrade_height, "height_ag", 1.0, 'M')
    wallU_AG = cleanInputs(_wallAboveGrade_Uvalue, "Uvalue_ag", 1.0, 'W/M2K')
    wallHeight_BG = cleanInputs(_wallBelowGrade_height, "height_bg", 1.0, 'M')
    wallU_BG = cleanInputs(_wallBelowGrade_Uvalue, "Uvalue_bg", 1.0, 'W/M2K')
    floorU = cleanInputs(_basementFloor_Uvalue, "Uvalue", 1.0, 'W/M2K')
    ach = cleanInputs(_basementAirChange, "ACH", 0.2)
    vol = cleanInputs(_basementVolume, "Volume", 1.0, 'M3')
    
    # Sort out Perim Curve Inputs
    perimCrvs = []
    for i, crv in enumerate(_exposedPerimCrvs):
        try:
            perimCrvs.append( float(crv) )
        except:
            try:
                rhinoGuid = ghenv.Component.Params.Input[3].VolatileData[0][i].ReferenceID.ToString()
                perimCrvs.append( rhinoGuid )
            except:
                warning = 'Please input only curves, surfaces or numbers (list) for _exposedPerimCrvs'
                ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, warning)
    
    # See if any of the Zone includes at least one ExposedFloor surface?
    anyZoneincludesSuspendedFloor = False
    for zone in HBZoneObjects:
        thisZoneincludesSuspendedFloor = False
        for srfc in zone.surfaces:
            if srfc.srfType[srfc.type] == 'ExposedFloor':
                anyZoneincludesSuspendedFloor = True
                thisZoneincludesSuspendedFloor = True
                break
        
        # Create a new Floor Element & Update the with the HB Zone Params
        floorElement_ = PHPP_grnd_UnheatedBasement( zone.name, _floorSurfaces, perimCrvs, perimPsi, wallHeight_AG, wallU_AG, wallHeight_BG, wallU_BG, floorU, ach, vol )
        updateHBFloorElement(thisZoneincludesSuspendedFloor, _floorSurfaces, floorElement_, zone, 'ExposedFloor')
        
        for warning in floorElement_.getWarnings():
            ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, warning)
    
    if anyZoneincludesSuspendedFloor == False:
        msg = "I could not find any 'ExposedFloor' elements in any of the HB zones input? Are you sure\n"\
        "this is the right type of foundation? For now I will use the parameter values\n"\
        "input here, but maybe double check your Rhino surface assignments?"
        ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Remark, msg)
    
#-------------------------------------------------------------------------------
elif '4' in str(_type):
    # Set the input data Explicitly
    for input in ghenv.Component.Params.Input:
        if input.Name == '_exposedPerimPsiValue':
            for each in input.VolatileData.AllData(True):
                _exposedPerimPsiValue = each
        elif input.Name == '_wallCrawlSpace_height':
            for each in input.VolatileData.AllData(True):
                _wallCrawlSpace_height = each
        elif input.Name == '_wallCrawlSpace_Uvalue':
            for each in input.VolatileData.AllData(True):
                _wallCrawlSpace_Uvalue = each
        elif input.Name == '_crawlSpace_UValue':
            for each in input.VolatileData.AllData(True):
                _crawlSpace_UValue = each
        elif input.Name == '_ventilationOpeningArea':
            for each in input.VolatileData.AllData(True):
                _ventilationOpeningArea = each
        elif input.Name == '_windVelocityAt10m':
            for each in input.VolatileData.AllData(True):
                _windVelocityAt10m = each
        elif input.Name == '_windShieldFactor':
            for each in input.VolatileData.AllData(True):
                _windShieldFactor = each
    
    # Clean user inputs
    perimPsi = cleanInputs(_exposedPerimPsiValue, 'psi', None, 'W/MK')
    wallHeight = cleanInputs(_wallCrawlSpace_height, "height", 1.0, 'M')
    wallU = cleanInputs(_wallCrawlSpace_Uvalue, "Uvalue", 1.0, 'W/M2K')
    crawlspaceU = cleanInputs(_crawlSpace_UValue, "Ucrawl", 5.9, 'W/M2K')
    ventOpening = cleanInputs(_ventilationOpeningArea, "ventOpening", 1.0, 'M2')
    windVelocity = cleanInputs(_windVelocityAt10m, "velocity", 4.0)
    windFactor = cleanInputs(_windShieldFactor, "windFactor", 0.05)
    
    # Sort out Perim Curve Inputs
    perimCrvs = []
    for i, crv in enumerate(_exposedPerimCrvs):
        try:
            perimCrvs.append( float(crv) )
        except:
            try:
                rhinoGuid = ghenv.Component.Params.Input[3].VolatileData[0][i].ReferenceID.ToString()
                perimCrvs.append( rhinoGuid )
            except:
                warning = 'Please input only curves, surfaces or numbers (list) for _exposedPerimCrvs'
                ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, warning)
    
    # See if any of the Zone includes at least one ExposedFloor surface?
    anyZoneincludesSuspendedFloor = False
    for zone in HBZoneObjects:
        thisZoneincludesSuspendedFloor = False
        for srfc in zone.surfaces:
            if srfc.srfType[srfc.type] == 'ExposedFloor':
                anyZoneincludesSuspendedFloor = True
                thisZoneincludesSuspendedFloor = True
                break
        
        # Create a new Floor Element & Update the with the HB Zone Params
        floorElement_ = PHPP_grnd_SuspendedFloor( zone.name, _floorSurfaces, perimCrvs, perimPsi, wallHeight, wallU, crawlspaceU, ventOpening, windVelocity, windFactor)
        updateHBFloorElement(thisZoneincludesSuspendedFloor, _floorSurfaces, floorElement_, zone, 'ExposedFloor')
        
        for warning in floorElement_.getWarnings():
            ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Warning, warning)
    
    if anyZoneincludesSuspendedFloor == False:
        msg = "I could not find any 'ExposedFloor' elements in any of the HB zones input? Are you sure\n"\
        "this is the right type of foundation? For now I will use the parameter values\n"\
        "input here, but maybe double check your Rhino surface assignments?"
        ghenv.Component.AddRuntimeMessage(ghK.GH_RuntimeMessageLevel.Remark, msg)

#-------------------------------------------------------------------------------
# Add modified Surfaces / Zones back to the HB dictionary
if len(_HBZones)>0:
    HBZones_  = hb_hive.addToHoneybeeHive(HBZoneObjects, ghenv.Component)

# Preview
if floorElement_ != None:
    print repr(floorElement_)
    preview(floorElement_)