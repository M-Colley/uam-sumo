# Urban Air Mobility in SUMO

## Added Features

- Script to automatically create Urban Air Mobility hubs
  - Given a valid sumocfg and a list of coordinates, we automatically generate UAM hubs at those coordinates
  - All hubs are directly connected to each other, without any interaction with the standard road network
  - Each hub is reachable for pedestrians in the simulation by foot
  - We added a custom Air Taxi vehicle type, extending SUMO's taxi. Relevant parameters, such as its person capacity, maximum speed and emission class can be adjusted
  - The custom Air Taxis, called uamtaxi, automatically select the best UAM hub to return to, after delivering their customer. The hub selection parameters are also adjustable
- Addition of a hub based Air Taxi service
  - An adjustable percentage of vehicles in the simulation get converted to pedestrians, trying to reach their destination by using the Air Taxi service
  - Air Taxis start their flight either when the taxi reaches maximum capacity, or a pedestrian has waited a configurable amount of time
- Extensive logging for scientific studies

## How to use

### Prerequisites

- sumo installed (requires version released on 01.08.2024 or newer, 1.20 contains a bug that was fixed later)
- [rtree](https://github.com/Toblerity/rtree) installed (see requirements.txt)
- [Python](https://www.python.org/downloads) installed
- installed sumo additions (run ``pip install -r "%PYTHONPATH%\requirements.txt" --upgrade`` under WINDOWS)

### Adding UAM hubs to network

1. valid `.sumocfg` with sumo network and at least one route and additionals file specified (unzipped files)
2. decide on uam hub coordinates, fitting to sumo network. For example using netedit
3. run "createUamHubs.py" with desired sumocfg and coordinates. For example: ` py .\createUamHubs.py <path_to_sumocfg>\sim.sumocfg 6200 2000 8500 3600 6300 5150` will create UAM hubs at (6200, 2000), (8500, 3600) and (3600, 5150). Alternatively add `--help` for more info.
4. new sumocfg with added hubs is called `<hub_count>_uam_hubs_<previous_name>.sumocfg`

Keep in mind that the specified coordinates should not be further apart from all others, than specified in ``uamHubConfig.py``. Hubs are only connected when they are within the `uam_hub_connection_radius` of another UAM hub.

Many UAM hub specific variables can be configured in ``uamHubConfig.py`` to adjust the creation of the UAM hubs. These changes are only applied upon calling `createUamHubs.py` anew.


### Running the simulation

Run the simulation by calling ``py uamTraCI.py``.
Without any further arguments, the default settings configured in the `simConfig.py` will be used.
For the available command line parameters, run ``py uamTraCI.py --help``.

Custom scenarios, for example ones created using `createUamHubs.py`, can be run by adding the
`--scenario_path <path_to_scenario>` command line option.

Example command:
``py uamTraCI.py --nogui --loop --uam_step_size 0.05 --uam_start_density 0.0 --uam_upper_bound 0.3 --scenario_path .\scenarios\manhattan\5_uam_hubs_manhattan.sumocfg``

If further adjustments to the parameters used during the simulation are desired, edit `simConfig.py` as needed.

## Add LLM support

Currently, vehicles defined in the `route file` are converted to UAM customers, with a chance of `uam_density`.
To achieve this, the vehicles start and destination point are looked at.
If the start and/or destination edge don't allow for pedestrian access, an alternative edge in a small radius (see `simConfig.py`) is looked for (`find_alternative_edge()`).
Once a valid start and end point are found, we call `traci.simulation.findIntermodalRoute(start_edge, dest_edge, modes="taxi")`, to generate stages for a potential intermodal route from start to dest.
If one of the stages contains an UAM taxi, travel by Air Taxi is faster than walking.
For more detail, see `create_uam_customers()`.

Assuming we don't want to convert vehicles for LLM, but add additional pedestrians to the simulation, we need a start and a destination.
The function we use to calculate our intermodal route is `traci.simulation.findIntermodalRoute()`. Passing `modes="taxi"` searches for routes using "walking" and "taxi" (in our case Air Taxi). More can be added.
This function requires the start and destination in the form of an edge. To find an edge near a location, we can use `net.getNeighboringEdges()`, where `net = sumolib.net.readNet(net_file)`, with a radius of our choosing.

`findIntermodalRoute` returns a list of "stages", which have to be looked at first.
(Note: a stage containing taxi travel for example can only be generated if a valid taxi exist in the simulation at the time the function is called, likewise for other travel modes).
Stage object contain the following information: 
`stage: {type, vType, line, destStop, edges, travelTime, cost, length, intended, depart, departPos, arrivalPos, description})`.

If no stages are returned, there is no valid route from start to dest.
If there is only one stage returned, no change in mode will happen and only the `vType` will be used.
Lastly, the returned list contains multiple stages: Information like estimated `travelTime` and the type of travel 
can be extracted from each stage element to use in the decision-making of the LLM. 
These stage objects can be altered at will. For example if 3 stages in the following order are generated:
`passenger`, `taxi`(Air Taxi), `passenger`, but the LLM instead wants to walk to the UAM hub, we can create a new stage 
instead of the first stage, using the given information. Keep in mind that the selected edges have to allow the desired vType. 
We can extract the first and the last edge of the initial car route, and generate a new one for pedestrians using 
`traci.simulation.findRoute()`, given the start end destination edge allow the new vType. 

Lastly we need to create the new entity and add the desired stages. For example for pedestrians that can be achieved by
calling `traci.person.add(new_id, start_edge, pos=0, depart=current_time)` and `traci.person.appendStage(new_id, stages)`. This should be identical with other vTypes.

If changes to the route/stages are desired afterward, for example after a pedestrian arrives at the destination UAM hub, 
the previously mentioned functions can be called again and used to alter the pedestrian. Currently, the following stage 
transitions are registered in my code:
- pedestrian stopped walking and started waiting -> arrived at UAM hub
- pedestrian stopped waiting and started flying -> entered Air Taxi
- pedestrian stopped flying and started walking -> left Air Taxi
- pedestrian left simulation -> arrived at destination

Currently, these are used for logging purposes, but can be extended with LLM decision-making if so desired.

## Results after a simulation

After every simulation, a new folder inside the 'results' directory will be created in which you can find several result files:
- uam-log.csv (logged every stage change of UAM customers):
  - timestamp: date
  - step: integer
  - scenario: string
  - pedestrianID (ID of newly created UAM customer): string
  - vehicleID (ID of vehicle if aboard one): string
  - state: 'noRoute': no valid route could be found, 'onlyWalking': using an Air Taxi is slower than walking, 'walking', 'waiting', 'flying', 'terminated': UAM customer left the simulation
  - x: integer
  - y: integer
  - routeStartX (original starting point): integer
  - routeStartY (original starting point): integer
  - routeDestX: integer
  - routeDestY: integer
  - originalVehicleID: string
  - uamDensity (percentage of vehicles converted to UAM customers): float
  - uam_vehicles_per_hub (initial Air Taxi count at each hub): integer
  - uam_vehicle_capacity: integer
  - group_finding_time: integer
  - uam_hub_count (amount of UAM hubs identified in the simulation): integer
- uam-taxi-log.csv (logged the state of Air Taxis in every step)
  - timestamp: date
  - step: integer
  - scenario: string
  - vehicleID: string
  - state:
  - x: integer
  - y: integer
  - pedCount (amount of customers aboard the Air Taxi): integer
  - customerIds: list(string)
  - uamHubCount (amount of UAM hubs identified in the simulation): integer
  
