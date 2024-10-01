#!/usr/bin/env python
import os

results_folder_path = os.path.join("results")   # path where simulation results are stored

scenarios = {
    "test": os.path.join("scenarios", "taxiTesting2", "taxiTesting2.sumocfg"),
    "Ingolstadt": os.path.join("scenarios", "Ingolstadt", "simulation", "scooters_5_uam_hubs_24h_sim.sumocfg"),
    "Ulm": os.path.join("scenarios", "Ulm", "5_uam_hubs_osm.sumocfg"),
    "Manhattan": os.path.join("scenarios", "manhattan", "5_uam_hubs_manhattan.sumocfg"),
    "disconnected": os.path.join("scenarios", "Ingolstadt", "simulation", "removed_connections.sumocfg")
}
scenario = "Ingolstadt"

no_gui = False                  # whether sumo should be run using sumo-gui or on command line
step_length = 1                 # granularity of simulation. Defines the step length in seconds
loop = False                    # whether the simulation should be run multiple times in a row, looping through densities
exact_distance_calculation = False   # whether the exact distance should be calculated when determining the distance between an escooter to all other pedestrians on the same lane
seconds_to_simulate = 7200      # maximum amount of seconds simulated
verbosity = 2                   # verbosity of command line output: 0 = NONE, 1 = SPARSE, 2 = NORMAL, 3 = VERBOSE
uam_vehicles_per_hub = 5        # amount of Air Taxis generated at each uam hub
uam_vehicle_capacity = 4        # max amount of pedestrians in an uam vehicle at the same time
group_finding_time = 180        # max time in sec that is waited to build a larger group before starting a flight
lateral_resolution = 0.7        # divides the lanes into x meter wide strips, necessary for bicycles to be able to pass vehicles on the right side of the road. 0.7 allows normal bicycles (width 0.65) to pass
alternative_edge_radius = 300   # radius in meter around the from-junction when looking for an alternative edge for vehicle to uam pedestrian conversion
uam_hub_count = "NULL"
conversion_vClasses = ['passenger', 'private', 'motorcycle', 'moped', 'evehicle', 'hov']  # list of vClasses eligible for conversion to uam/mm users


#--- loop and density settings ---#
uam_step_size = 0.1         # default step size for each loop iteration for the uam customer density in the simulation
uam_start_density = 0.3     # default start uam customer density when looping through multiple simulations
uam_upper_bound = 0.5       # default upper bound for the uam customer density when looping through multiple simulations
uam_density = uam_start_density

#--- Logging ---#
# The following variables decide if the appropriate result file will be written or not (after the simulation)
outputFilesActive = True        # If false, turns off all following output files:

statsOutput = True              # more overall statistics of the entire simulation
summaryOutput = True            # information about the current state of the simulation (vehicle count etc.)
tripinfoOutput = True           # aggregated information about each vehicle's journey (optionally with emission data)
vehroutesOutput = True          # information about each vehicle's routes over simulation run
personsummaryOutput = True      # information about the current state of persons the simulation (person count etc.)
fullOutput = False              # various information for all edges, lanes and vehicles (good for visualization purposes)
ndumpOutput = False             # contains detailed information for each edge, each vehicle and each simulation step
fcdOutput = False               # Floating Car Data includes name, position, angle and type for every vehicle
queueOutput = False             # lane-based calculation of the actual tailback in front of a junction
edgedataOutput = False          # edge-based network performance measures
lanedataOutput = False          # lane-based network performance measures
lanechangeOutput = False        # Lane changing events with the associated motivation for changing for every vehicle
amitranOutput = False           # edge/lane-based network performance measures following the Amitran standard
linkOutput = False              # saves debugging data for the intersection model. This data reveals how long each vehicle intends to occupy an upcoming intersection.
personinfoOutput = False        # Save person info and container info
emissionOutput = False          # emission values of all vehicles for every simulation step