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
Takes in a list of Honeybee zones and outputs print-ready (floor plan) objects for the Treated Floor Area (TFA). Will pull out any 'PHPP Room' information from the zones and create surfaces, color them by TFA factor, and create room-tags based on the data. Be sure you've used the 'Create PHPP Rooms' to assign parameters to the zones and geometry correctly before trying to use this.
-
EM June 22, 2020
    Args:
        _HBZones: A list of the Honeybee zone objects which are being analyzed in the model.
        colors_: <not used yet>
    Returns:
        filenames_: A list of autogenerated Filenames for use if you want.
        geom_: A Tree of the TFA surfaces as Meshes, colored by TFA Factor. Each branch of the tree will become a separate page in the final PDF. Connect to the '_geomToBake' input on the '2PDF | Print' component
        annotationTxt_: A Tree of Room Data tags for printing. Connect to the '_notesToBake' input on the '2PDF | Print' component
        annotationCP_: A Tree of Room center points (X,Y,Z). Useful for locating Room Tag information. Connect to the '_noteLocations' input on the '2PDF | Print' component
        tableHeaders_: A list of the Headers for the Data Table
        tableData_: A Tree of all the data for the Data Table. Each Branch corresponds to one row in the table (one room)
"""
ghenv.Component.Name = "BT_2PDF_TFAPlans"
ghenv.Component.NickName = "2PDF | TFA Plans"
ghenv.Component.Message = 'JUN_22_2020'
ghenv.Component.IconDisplayMode = ghenv.Component.IconDisplayMode.application
ghenv.Component.Category = "BT"
ghenv.Component.SubCategory = "03 | PDF"

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Grasshopper.Kernel as ghK
from System import Object
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path
import ghpythonlib.components as ghc

def roomCenterPt(_srfcs):
    srfcCenters = []
    for eachSrfc in _srfcs:
        srfcCenters.append(ghc.Area(eachSrfc).centroid)
    roomCenter = ghc.Average(srfcCenters)
    
    return roomCenter

def colorMeshFromRoom(_room):
    """Returns a mesh, colored by some logic
    
    Takes in a room, converts it to 
    a mesh and colors it depending on the srfcs TFA
    """
    
    room_srfcs_colored = []
    for srfcCount, srfc in enumerate(_room.TFAsurface):
        srfc_tfaFactor = _room.TFAfactors[srfcCount]
        
        if srfc_tfaFactor > 0.6:
            color = ghc.ColourRGB(255,255,255,17)
        elif srfc_tfaFactor <= 0.6 and srfc_tfaFactor > 0.5:
            color = ghc.ColourRGB(255,189,103,107)
            #color = ghc.ColourRGB(255,189,103,107)
        elif srfc_tfaFactor <= 0.5 and srfc_tfaFactor > 0.3:
            color = ghc.ColourRGB(255,154,205,50)
        elif srfc_tfaFactor <= 0.5 and srfc_tfaFactor > 0.3:
            color = ghc.ColourRGB(255,0,255,127)
        elif srfc_tfaFactor == 0:
            color = ghc.ColourRGB(255,238,130,238)
        else:
            color = ghc.ColourRGB(255,238,130,238)
        
        room_srfcs_colored.append( ghc.MeshColours(srfc, color) )
    
    return room_srfcs_colored

hb_hive = sc.sticky["honeybee_Hive"]()
HBZoneObjects = hb_hive.callFromHoneybeeHive(_HBZones)

filenames_ = []
geom_ = DataTree[Object]()
annotationCP_ = DataTree[Object]()
annotationTxt_ = DataTree[Object]()
tableHeaders_ = DataTree[Object]()
tableData_ = DataTree[Object]()

if HBZoneObjects:
    # Sort the zones by name. Grr.....
    HBZoneObjects_sorted = sorted(HBZoneObjects, key=lambda zone: zone.name)
    
    for zoneBranchNum, zone in enumerate(HBZoneObjects):
        filenames_.append('TFA FLOOR PLANS {}'.format(zoneBranchNum+1))
        
        for roomBranchNum, room in enumerate(zone.PHPProoms):
            # For each room, look at each surface in the room, convert it to
            # a mesh, and re-color it based on the type of ventilation airflow
            # (supply, extract, transfer). When done, add the new mesh to
            # and output tree 'geom_' for passing
            
            
            
            geom_.AddRange(colorMeshFromRoom(room), GH_Path(zoneBranchNum))
            
            
            # For each room, pull out the relevant data for a tag that will go
            # right ontop of surface in the final PDF. Also get the
            # Center Point for each annotation tag
            
            annotationTxt = "{}-{}\nTFA: {:.01f}m2".format(room.RoomNumber, room.RoomName, room.FloorArea_TFA)
            annotationTxt_.Add(annotationTxt, GH_Path(zoneBranchNum))
            annotationCP_.Add(roomCenterPt(room.TFAsurface), GH_Path(zoneBranchNum))
            
            
            # Get the Room's parameters and add to the Table
            roomData = [[room.HostZoneName,'ZONE'],
                            [room.RoomNumber, 'NUMBER'],
                            [room.RoomName, 'NAME'],
                            [room.FloorArea_Gross,'AREA (m2)'],
                            [room.RoomTFAfactor,'TFA FACTOR'],
                            [room.FloorArea_TFA,'TFA (m2)'],
                            [room.RoomNetClearVolume,'Vn50 (m3)'],
                            [room.RoomVentedVolume,'Vv (m3)'],
                            [room.RoomClearHeight,'CLG HEIGHT (m)']
                            ]
            if tableHeaders_.BranchCount == 0:
                tableHeaders_.AddRange([v[1] for i, v in enumerate(roomData)], GH_Path(0))
            tableData_.AddRange([v[0] for i, v in enumerate(roomData)], GH_Path(tableData_.BranchCount+1))
