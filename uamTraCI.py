#!/usr/bin/env python
import csv
import math
import os
import sys
import argparse
import random
from datetime import datetime
from enum import IntEnum
import xml.etree.ElementTree as ET
import simConfig as config
import uamHubConfig

# we need to import some python modules from the $SUMO_HOME/tools directory
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

from sumolib import checkBinary  # Checks for the binary in environ vars
import traci
import sumolib


class FloatRange(object):
    def __init__(self, start, end):
        self.start = start
        self.end = end

    def __eq__(self, other):
        return self.start <= other <= self.end

    def __contains__(self, item):
        return self.__eq__(item)

    def __iter__(self):
        yield self

    def __repr__(self):
        return '[{0},{1}]'.format(self.start, self.end)


def get_options():
    """
    Command line options using the argparse library
    """
    arg_parser = argparse.ArgumentParser()
    uam_group = arg_parser.add_argument_group("uam options")
    micromobility_group = arg_parser.add_argument_group("micromobility options")
    loop_group = arg_parser.add_argument_group("loop options")
    arg_parser.add_argument("--nogui", action="store_true", default=False, help="run the commandline version of sumo")
    arg_parser.add_argument("-v", "--verbosity", dest="verbosity", type=str,
                            choices=("none", "sparse", "normal", "verbose"),
                            help="Default = " + str(config.verbosity) + " verbosity of the command line output.")
    arg_parser.add_argument("--scenario", dest="scenario", type=str,
                            choices=config.scenarios.keys(),
                            help="Default = " + config.scenario + ". Defines the scenario you want to simulate. "
                                                                  "Choices are: " + str(list(config.scenarios.keys())))

    arg_parser.add_argument("--scenario_path", dest="scenario_path", type=str,
                            help="Alternative to --scenario: defines the path to the .sumoconfigg you want to simulate. "
                                 "Value should be an existing path to a valid .sumoconfigg file.")

    arg_parser.add_argument("--time_steps", dest="time_steps", type=int,
                            help="Default = " + str(
                                config.seconds_to_simulate) + ". Defines the amount of seconds simulated after which the simulation will terminate. "
                                                              "Does not equal real time seconds. A value of 3600 would mean that one hour would get "
                                                              "simulated.")

    arg_parser.add_argument("--step_length", dest="step_length", type=int,
                            help="Default = " + str(
                                config.step_length) + ". Defines the length of each simulated step. "
                                                      "Setting this to 1 equals one step per simulated second. 0.25 equals four steps. "
                                                      "This setting heavily impacts simulation time and complexity.")

    uam_group.add_argument("--uam_vehicles_per_hub", dest="uam_vehicles_per_hub", type=int,
                           help="Default = " + str(
                               config.uam_vehicles_per_hub) + ". Defines the amount of uam vehicles generated per uam hub. "
                                                              "Should be lower than the maximum capacity of the parking areas for the uam taxis.")

    uam_group.add_argument("--uam_vehicle_capacity", dest="uam_vehicle_capacity", type=int,
                           help="Defines the amount of pedestrians that are able to board an uam vehicles at the same "
                                "condition is fulfilled first.")

    uam_group.add_argument("--group_finding_time", dest="group_finding_time", type=int,
                           help="Default = " + str(
                               config.group_finding_time) + ". Defines the maximum time in seconds that a pedestrian intent on boarding an uam "
                                                            "vehicle has to wait for other potential passengers that want to fly to the same "
                                                            "destination until boarding the uam vehicle.")

    micromobility_group.add_argument("--lateral_resolution", dest="lateral_resolution", type=float,
                                     help="Default = " + str(
                                         config.lateral_resolution) + "Defines the resolution in meters which divides a lane into one or more sublanes."
                                                                      "For example if three bicycles should be able to ride side by side on a 3m wide lane,"
                                                                      " the lateral resolution must not be higher than 1.0."
                                                                      "It is recommended to set the lateral resolution to a value that divides the lane "
                                                                      "width evenly to avoid artifacts from varying stripe width."
                                                                      "The smaller this value is, the higher the running time.")

    loop_group.add_argument("-l", "--loop", action="store_true", dest="loop",
                            help="Default = " + str(
                                config.loop) + ". Run the simulation multiple times in a row, looping through uam and micromobility density.")
    loop_group.add_argument("--uam_step_size", dest="uam_step_size", type=float,
                            choices=FloatRange(0.0, 1.0),
                            help="default = " + str(
                                config.uam_step_size) + ". Only useful when the --loop option is set. "
                                                        "Defines the step size for the density of uam users in the loop. "
                                                        "Value should be between 0.0 and 1.0 as float. "
                                                        "Setting this value to exactly 0.0 disables looping over av_density instead. ")
    loop_group.add_argument("--mm_step_size", dest="mm_step_size", type=float,
                            choices=FloatRange(0.0, 1.0),
                            help="default = " + str(
                                config.mm_step_size) + ". Only useful when the --loop option is set. "
                                                       "Defines the step size for the density of micromobility users in the loop."
                                                       "Value should be between 0.0 and 1.0 as float. "
                                                       "Setting this value to exactly 0.0 disables looping over this variable instead.")
    loop_group.add_argument("--uam_start_density", dest="uam_start_density", type=float,
                            choices=FloatRange(0.0, 1.0),
                            help="default = " + str(config.uam_start_density) + ". "
                                                                                "Only useful when combined with the --loop option. Defines the lower bound for the "
                                                                                "used uam density in the loop. Value should be between 0.0 and 1.0 as float.")
    loop_group.add_argument("--mm_start_density", dest="mm_start_density", type=float,
                            choices=FloatRange(0.0, 1.0),
                            help="default = " + str(config.mm_start_density) + ". "
                                                                               "Only useful when combined with the --loop option. Defines the lower bound for the "
                                                                               "used micromobility density in the loop. "
                                                                               "Value should be between 0.0 and 1.0 as float.")
    loop_group.add_argument("--uam_upper_bound", dest="uam_upper_bound", type=float,
                            choices=FloatRange(0.0, 1.0),
                            help="default = " + str(config.mm_start_density) + ". "
                                                                               "Only useful when combined with the --loop option. Defines the upper bound for the "
                                                                               "used uam density in the loop. "
                                                                               "Value should be between 0.0 and 1.0 as float.")
    loop_group.add_argument("--mm_upper_bound", dest="mm_upper_bound", type=float,
                            choices=FloatRange(0.0, 1.0),
                            help="default = " + str(config.mm_start_density) + ". "
                                                                               "Only useful when combined with the --loop option. Defines the upper bound for the "
                                                                               "used micromobility density in the loop. "
                                                                               "Value should be between 0.0 and 1.0 as float.")

    args = arg_parser.parse_args()
    return args


class Verbosity(IntEnum):
    NONE = 0
    SPARSE = 1
    NORMAL = 2
    VERBOSE = 3


def check_for_new_reservations(reservation_dict, step, uam_log_writer, waiting_peds, uam_log_dict):
    new_reservations = traci.person.getTaxiReservations(1)
    for new_reservation in new_reservations:
        plan_dispatch(new_reservation, reservation_dict, step, uam_log_writer, waiting_peds, uam_log_dict)


def plan_dispatch(new_reservation, reservation_dict, step, uam_log_writer, waiting_peds: set[str], uam_log_dict):
    from_edge = new_reservation.fromEdge
    to_edge = new_reservation.toEdge
    person_id = new_reservation.persons[0]
    if (from_edge, to_edge) not in reservation_dict:
        reservation_dict_entry = {"total_waiting_time": 0, "waiting_ped_count": 1,
                                  "id_list": [person_id],
                                  "reservation_id_list": [new_reservation.id]}
        reservation_dict[from_edge, to_edge] = reservation_dict_entry
    else:
        reservation_dict[from_edge, to_edge]["waiting_ped_count"] += 1
        reservation_dict[from_edge, to_edge]["id_list"].append(person_id)
        reservation_dict[from_edge, to_edge]["reservation_id_list"].append(new_reservation.id)
    if config.verbosity >= Verbosity.VERBOSE:
        print("The following pedestrians issued a UAM taxi reservation in the current step: " + str(person_id))

    try:
        waiting_peds.add(person_id)
        entry = [datetime.now(), step, config.scenario, person_id, "NULL", "waiting",
                 round(traci.person.getPosition(person_id)[0]), round(traci.person.getPosition(person_id)[1]),
                 uam_log_dict[person_id]['routeStartX'], uam_log_dict[person_id]['routeStartY'],
                 uam_log_dict[person_id]['routeDestX'], uam_log_dict[person_id]['routeDestY'],
                 uam_log_dict[person_id]['originalVehicleId'], config.uam_density, config.mm_density,
                 config.uam_vehicles_per_hub, config.uam_vehicle_capacity, config.group_finding_time,
                 config.uam_hub_count]
        uam_log_writer.writerow(entry)
    except:
        print("Error: uam_log.csv row not written. Problem with person \"" + person_id + "\".")


def increment_reservation_waiting_time(reservation_dict):
    for entry in reservation_dict:
        reservation_dict[entry]["total_waiting_time"] += config.step_length


def dispatch_uam_vehicles(reservation_dict, parking_area_edges):
    to_delete_entries = []
    for entry in reservation_dict:
        if (reservation_dict[entry]["total_waiting_time"] >= config.group_finding_time
                or reservation_dict[entry]["waiting_ped_count"] >= config.uam_vehicle_capacity):
            reservations = (reservation_dict[entry]["reservation_id_list"]
                            + reservation_dict[entry]["reservation_id_list"])
            # TODO: limit to veh capacity
            starting_coordinate = traci.person.getPosition(reservation_dict[entry]["id_list"][0])
            closest_taxi = get_best_uam_vehicle(entry[0], parking_area_edges, starting_coordinate)
            if closest_taxi == "error":
                continue
            traci.vehicle.dispatchTaxi(closest_taxi, reservations)
            to_delete_entries.append(entry)
    for to_delete_entry in to_delete_entries:
        del reservation_dict[to_delete_entry]


def get_best_uam_vehicle(from_edge, parking_area_edges, starting_coordinate):
    # iterate over parking areas on departure edge
    # for parking_area in (parking_area_edges[from_edge]):
    for parking_area in (parking_area_edges["-" + from_edge]):
        # get taxis currently parked at the current parking area
        parking_taxis = traci.parkingarea.getVehicleIDs(parking_area)
        if len(parking_taxis) != 0:
            for taxi in parking_taxis:
                # check if taxi has no pending reservation
                if taxi in traci.vehicle.getTaxiFleet(0):
                    return taxi

    # no taxi is available at a parking area at the departure edge, search for alternative taxi
    closest_distance = 100000000
    closest_taxi = "none"
    for parking_area in traci.parkingarea.getIDList():
        # only look at taxi parking areas
        if "uam" not in parking_area:
            continue
        for taxi in traci.parkingarea.getVehicleIDs(parking_area):
            distance = math.dist(starting_coordinate, traci.vehicle.getPosition(taxi))
            if distance < closest_distance:
                closest_distance = distance
                closest_taxi = taxi

    if closest_taxi != "none":
        return closest_taxi
    else:
        return "error"


def find_newly_added_escooters(new_vehicles: set[str], escooters: set[str]):
    # iterate through vehicles added in current step
    for new_vehicle in new_vehicles:
        if traci.vehicle.getTypeID(new_vehicle) == "escooter":
            # add vehicle id to list of escooters
            escooters.add(new_vehicle)


def select_escooter_lane(escooters: set[str]):
    for escooter in escooters:
        current_lane = traci.vehicle.getLaneID(escooter)
        current_edge = traci.lane.getEdgeID(current_lane)
        lane_count = traci.edge.getLaneNumber(current_edge)
        # nothing to do if only one lane exists
        if lane_count == 1:
            continue
        lane_information = {}
        bicycle_only_exists = False
        for lane_index in range(lane_count):
            lane_id = current_edge + '_' + str(lane_index)
            allowed_veh_types = traci.lane.getAllowed(lane_id)
            # check if bicycles are in allowed vehicles at all
            if "bicycle" not in allowed_veh_types:
                lane_information[lane_index] = {"lane_type": "prohibited",
                                                "occupancy": 1}
                continue
            # check if lane bicycle only lane
            if len(allowed_veh_types) == 1:  # TODO: maybe better way to find bicycle only
                bicycle_only_exists = True
                # change to the bicycle only lane
                traci.vehicle.changeLane(escooter, lane_index, config.escooter_lane_change_duration)
            # check if lane is a sidewalk
            elif ("pedestrian" in allowed_veh_types) and (
                    "passenger" not in allowed_veh_types):  # TODO: maybe better way to find sidewalk
                gather_lane_information(current_edge, lane_id, lane_index, lane_information, "sidewalk")
            # neither sidewalk nor bicycle only lane, but allows bicycles
            else:
                gather_lane_information(current_edge, lane_id, lane_index, lane_information, "standard")
        if bicycle_only_exists:
            # already changed lane to bicycle lane -> nothing to do
            continue
        else:
            best_lane_index = select_preferred_lane(lane_information)
            if best_lane_index != -1:  # avoid changing to prohibited lanes
                traci.vehicle.changeLane(escooter, best_lane_index, config.escooter_lane_change_duration)
                print(escooter + " changed lane to index " + str(best_lane_index))


def select_preferred_lane(lane_information: dict) -> int:
    highest_lane_rating = 0
    best_lane_index = -1
    for lane_index in lane_information:
        lane_rating = calculate_lane_rating(lane_information[lane_index])
        if lane_rating > highest_lane_rating:
            highest_lane_rating = lane_rating
            best_lane_index = lane_index
    return best_lane_index


def calculate_lane_rating(lane_information_entry: dict) -> float:
    if lane_information_entry["lane_type"] == "sidewalk":
        if lane_information_entry["occupancy"] <= config.escooter_sidewalk_occupancy_threshold:
            # low occupancy sidewalk
            return 1
        else:
            # high occupancy sidewalk
            return 0.6
    elif lane_information_entry["lane_type"] == "standard":
        if lane_information_entry["occupancy"] <= config.escooter_road_occupancy_threshold:
            # low occupancy road
            return 0.9
        if lane_information_entry["mean_speed"] <= config.escooter_road_speed_threshold:
            if lane_information_entry["mean_length"] <= config.escooter_road_vehicle_length_threshold:
                # high occupancy road, slow moving, small vehicles
                return 0.8
            else:
                # high occupancy road, slow moving, large vehicles
                return 0.7
        else:
            if lane_information_entry["mean_length"] <= config.escooter_road_vehicle_length_threshold:
                # high occupancy road, fast moving, small vehicles
                return 0.5
            else:
                # high occupancy road, fast moving, large vehicles
                return 0.4
    else:
        # prohibited road or unmarked scenario
        return -1.0


def gather_lane_information(edge_id: str, lane_id: str, lane_index: int, lane_information: dict, lane_type: str):
    if lane_type == "sidewalk":
        occupancy_rate = len(traci.edge.getLastStepPersonIDs(edge_id)) / traci.lane.getLength(lane_id)
    else:
        occupancy_rate = traci.lane.getLastStepOccupancy(lane_id)
    mean_speed = traci.lane.getLastStepMeanSpeed(lane_id)
    mean_length = traci.lane.getLastStepLength(lane_id)
    lane_information[lane_index] = {"lane_type": lane_type,
                                    "occupancy": occupancy_rate,
                                    "mean_speed": mean_speed,
                                    "mean_length": mean_length}


def create_uam_taxis(parking_area_edges):
    parking_areas = traci.parkingarea.getIDList()
    for parking_area in parking_areas:
        if (parking_area == uamHubConfig.fake_parking_area_id) or "uam" not in parking_area:
            continue
        edge_id = traci.lane.getEdgeID(traci.parkingarea.getLaneID(parking_area))
        parking_area_edges.setdefault(edge_id, set()).add(parking_area)
        route_id = parking_area + "_route"
        traci.route.add(route_id, [edge_id])
        traci.route.setParameter(parking_area + "_route", "stop", parking_area)
        for x in range(config.uam_vehicles_per_hub):
            traci.vehicle.add("uam_taxi_" + parking_area + "_" + str(x), route_id, "uamtaxi")


def recolour_uam_taxis():
    for idle_taxi in traci.vehicle.getTaxiFleet(0):
        traci.vehicle.setColor(idle_taxi, (0, 255, 0, 255))
    for on_route_taxi in traci.vehicle.getTaxiFleet(1):
        traci.vehicle.setColor(on_route_taxi, (0, 255, 255, 255))
    for active_taxi in traci.vehicle.getTaxiFleet(2):
        traci.vehicle.setColor(active_taxi, (255, 0, 0, 255))


def create_uam_customers(new_vehicles: set[str], step, uam_log_writer, uam_customers: set[str], uam_log_dict) -> set[
    str]:
    current_time = traci.simulation.getTime()
    removed_vehicles = set()
    for vehicle in new_vehicles:  # adjust all newly added vehicles
        if "taxi" not in traci.vehicle.getTypeID(
                vehicle) and random.random() <= config.uam_density:  # with a chance of <uam_density>
            new_id = vehicle + "_uam_ped"
            route = traci.vehicle.getRoute(vehicle)  # get route of vehicle. We need 1st and last edge
            start_edge = route[0]
            if not allowed_on_edge("taxi", start_edge):
                start_edge = find_alternative_edge(start_edge)
                if start_edge == "":  # no alternative found in config.alternative_edge_radius
                    if config.verbosity >= Verbosity.SPARSE:
                        print("Could not find an alternative start edge for " + vehicle + ". Skipping.")
                        continue
            dest_edge = route[-1]
            if not allowed_on_edge("taxi", dest_edge):
                dest_edge = find_alternative_edge(dest_edge)
                if dest_edge == "":  # no alternative found in config.alternative_edge_radius
                    if config.verbosity >= Verbosity.SPARSE:
                        print("Could not find an alternative destination edge for " + vehicle + ". Skipping.")
                        continue

            start_coords = traci.junction.getPosition(traci.edge.getFromJunction(start_edge))
            dest_coords = traci.junction.getPosition(traci.edge.getFromJunction(dest_edge))

            stages = traci.simulation.findIntermodalRoute(start_edge, dest_edge,
                                                          modes="taxi")  # calculate best route (using taxis) from 1st to last edge
            if len(stages) == 0:  # no route possible
                if config.verbosity >= Verbosity.VERBOSE:
                    print("Could not find a route from \"" + start_edge + "\" to \"" + dest_edge + "\". Skipping.")
                try:
                    entry = [datetime.now(), step, config.scenario, new_id, "NULL", "noRoute",
                             "NULL", "NULL", start_coords[0], start_coords[1], dest_coords[0], dest_coords[1],
                             vehicle, config.uam_density, config.mm_density,
                             config.uam_vehicles_per_hub, config.uam_vehicle_capacity, config.group_finding_time,
                             config.uam_hub_count]
                    uam_log_writer.writerow(entry)
                    continue
                except:
                    print("Error: uam_log.csv row not written at \"Could not find a route\"")
                    continue
            if len(stages) == 1:  # route possible, but uam not faster than walking         TODO: clean up duplicate code
                if config.verbosity >= Verbosity.VERBOSE:
                    print(
                        "Intermodal route with UAM taxi not faster on route from \"" + start_edge + "\" to \"" + dest_edge + "\". Walking the entire route.")
                traci.person.add(new_id, start_edge, pos=0, depart=current_time)  # adds new person to simulation
                traci.person.appendStage(new_id, stages[0])
                traci.vehicle.remove(vehicle)
                removed_vehicles.add(vehicle)
                uam_customers.add(new_id)

                uam_log_dict[new_id] = {'routeStartX': round(start_coords[0]),
                                        'routeStartY': round(start_coords[1]),
                                        'routeDestX': round(dest_coords[0]),
                                        'routeDestY': round(dest_coords[1]),
                                        'originalVehicleId': vehicle}
                if not config.no_gui:
                    traci.person.setColor(new_id, (255, 123, 0, 255))  # recolor new pedestrian for visual effect
                try:
                    entry = [datetime.now(), step, config.scenario, new_id, "NULL", "onlyWalking",
                             round(traci.person.getPosition(new_id)[0]), round(traci.person.getPosition(new_id)[1]),
                             round(start_coords[0]), round(start_coords[1]), round(dest_coords[0]),
                             round(dest_coords[1]),
                             vehicle, config.uam_density, config.mm_density,
                             config.uam_vehicles_per_hub, config.uam_vehicle_capacity, config.group_finding_time,
                             config.uam_hub_count]
                    uam_log_writer.writerow(entry)
                    continue
                except:
                    print("Error: uam_log.csv row not written at \"only walking\"")
                    continue
            if len(stages) >= 2:  # intermodal route with uam
                if config.verbosity >= Verbosity.SPARSE:
                    print("Removed \"" + vehicle + "\" and added \"" + new_id + "\" as a new UAM customer.\n"
                                                                                "Traveling from \"" + start_edge + "\" to \"" + dest_edge + "\".")
                traci.person.add(new_id, start_edge, pos=0, depart=current_time)  # adds new person to simulation
                for stage in stages:
                    traci.person.appendStage(new_id, stage)  # append all walking and driving stages to person
                traci.vehicle.remove(vehicle)
                removed_vehicles.add(vehicle)
                uam_customers.add(new_id)
                uam_log_dict[new_id] = {'routeStartX': round(start_coords[0]),
                                        'routeStartY': round(start_coords[1]),
                                        'routeDestX': round(dest_coords[0]),
                                        'routeDestY': round(dest_coords[1]),
                                        'originalVehicleId': vehicle}
                if not config.no_gui:
                    traci.person.setColor(new_id, (255, 0, 0, 255))  # recolor new pedestrian for visual effect
                try:
                    entry = [datetime.now(), step, config.scenario, new_id, "NULL", "walking",
                             round(traci.person.getPosition(new_id)[0]), round(traci.person.getPosition(new_id)[1]),
                             round(start_coords[0]), round(start_coords[1]), round(dest_coords[0]),
                             round(dest_coords[1]),
                             vehicle, config.uam_density, config.mm_density,
                             config.uam_vehicles_per_hub, config.uam_vehicle_capacity, config.group_finding_time,
                             config.uam_hub_count]
                    uam_log_writer.writerow(entry)
                    continue
                except:
                    print("Error: uam_log.csv row not written at \"intermodal route with uam\"")
                    continue

    return removed_vehicles


def allowed_on_edge(name: str, edge_id: str) -> bool:
    lane_count = traci.edge.getLaneNumber(edge_id)
    for lane_index in range(lane_count):
        lane_id = edge_id + '_' + str(lane_index)
        if name in traci.lane.getAllowed(lane_id):
            return True
    return False


def find_alternative_edge(edge_id: str) -> str:
    from_junction_coordinates = traci.junction.getPosition(traci.edge.getFromJunction(edge_id))
    nearby_edges = net.getNeighboringEdges(from_junction_coordinates[0], from_junction_coordinates[1],
                                           config.alternative_edge_radius, includeJunctions=False)
    if len(nearby_edges) > 0:
        nearby_edges_sorted = sorted([(dist, edge) for edge, dist in nearby_edges], key=lambda x: x[0])
    else:
        nearby_edges_sorted = nearby_edges
    for nearby_edge in nearby_edges_sorted:
        edge_id = nearby_edge[1].getID()
        if allowed_on_edge("pedestrian", edge_id):
            return edge_id
    return ""


def log_started_flights(uam_log_writer, step, waiting_peds: set[str], flying_peds: set[str], uam_log_dict) -> set[str]:
    to_remove_peds = set()
    for waiting_customer in waiting_peds:
        if traci.person.getVehicle(waiting_customer) != "":
            to_remove_peds.add(waiting_customer)
            flying_peds.add(waiting_customer)
            try:
                entry = [datetime.now(), step, config.scenario, waiting_customer,
                         traci.person.getVehicle(waiting_customer), "flying",
                         round(traci.person.getPosition(waiting_customer)[0]),
                         round(traci.person.getPosition(waiting_customer)[1]),
                         uam_log_dict[waiting_customer]['routeStartX'], uam_log_dict[waiting_customer]['routeStartY'],
                         uam_log_dict[waiting_customer]['routeDestX'], uam_log_dict[waiting_customer]['routeDestY'],
                         uam_log_dict[waiting_customer]['originalVehicleId'], config.uam_density, config.mm_density,
                         config.uam_vehicles_per_hub, config.uam_vehicle_capacity, config.group_finding_time,
                         config.uam_hub_count]
                uam_log_writer.writerow(entry)
                continue
            except:
                print("Error: uam_log.csv row not written when trying to log a started flight.")
    return to_remove_peds


def log_finished_flights(uam_log_writer, step, flying_peds: set[str], uam_log_dict) -> set[str]:
    to_remove_peds = set()
    for flying_customer in flying_peds:
        if traci.person.getVehicle(flying_customer) == "":
            to_remove_peds.add(flying_customer)
            try:
                entry = [datetime.now(), step, config.scenario, flying_customer, "NULL", "walking",
                         round(traci.person.getPosition(flying_customer)[0]),
                         round(traci.person.getPosition(flying_customer)[1]),
                         uam_log_dict[flying_customer]['routeStartX'], uam_log_dict[flying_customer]['routeStartY'],
                         uam_log_dict[flying_customer]['routeDestX'], uam_log_dict[flying_customer]['routeDestY'],
                         uam_log_dict[flying_customer]['originalVehicleId'], config.uam_density, config.mm_density,
                         config.uam_vehicles_per_hub, config.uam_vehicle_capacity, config.group_finding_time,
                         config.uam_hub_count]
                uam_log_writer.writerow(entry)
                continue
            except:
                print("Error: uam_log.csv row not written when logging finished flight")
    return to_remove_peds


def log_terminated_customers(uam_log_writer, step, terminated_peds: set[str], uam_log_dict):
    for terminated_ped in terminated_peds:
        try:
            entry = [datetime.now(), step, config.scenario, terminated_ped, "NULL", "terminated",
                     "NULL", "NULL",
                     uam_log_dict[terminated_ped]['routeStartX'], uam_log_dict[terminated_ped]['routeStartY'],
                     uam_log_dict[terminated_ped]['routeDestX'], uam_log_dict[terminated_ped]['routeDestY'],
                     uam_log_dict[terminated_ped]['originalVehicleId'], config.uam_density, config.mm_density,
                     config.uam_vehicles_per_hub, config.uam_vehicle_capacity, config.group_finding_time,
                     config.uam_hub_count]
            uam_log_writer.writerow(entry)
            continue
        except:
            print("Error: uam_log.csv row not written for terminated customer.")


def log_taxis(uam_taxi_log_writer, step):
    idle_taxis = traci.vehicle.getTaxiFleet(0)
    on_route_taxis = traci.vehicle.getTaxiFleet(1)
    active_taxis = traci.vehicle.getTaxiFleet(2)
    all_taxis = idle_taxis + on_route_taxis + active_taxis
    state = "error"
    ped_count = 0
    customers = "NULL"

    for taxi in all_taxis:
        if taxi in idle_taxis:
            state = "idle"
        if taxi in on_route_taxis:
            state = "onRoute"
        if taxi in active_taxis:
            state = "active"
            ped_count = traci.vehicle.getPersonNumber(taxi)
            customers = "-".join(traci.vehicle.getPersonIDList(taxi))
        try:
            entry = [datetime.now(), step, config.scenario, taxi, state, round(traci.vehicle.getPosition(taxi)[0]),
                     round(traci.vehicle.getPosition(taxi)[1]), str(ped_count), customers, config.uam_hub_count]
            uam_taxi_log_writer.writerow(entry)
            continue
        except:
            print("Error: uam_log.csv row not written for UAM taxi \"" + taxi + "\".")


def count_uam_hubs():
    parking_areas = traci.parkingarea.getIDList()
    uam_hub_count = 0
    for parking_area in parking_areas:
        if (parking_area == uamHubConfig.fake_parking_area_id) or "uam" not in parking_area:
            continue
        uam_hub_count += 1
    config.uam_hub_count = uam_hub_count


# contains TraCI control loop
def run():
    parking_area_edges = {}

    count_uam_hubs()
    create_uam_taxis(parking_area_edges)

    step = 0
    reservation_dict = {}
    escooters = set()
    uam_customers = set()
    last_step_vehicles = set()
    last_step_peds = set()
    waiting_peds = set()
    flying_peds = set()
    uam_log_dict = {}

    uam_ped_log_file_name = "uam-log-{}.csv".format(os.path.basename(results_folder))
    uam_ped_log_file_path = os.path.join(results_folder, uam_ped_log_file_name)
    uam_ped_log_file = open(uam_ped_log_file_path, 'w', newline='')

    uam_ped_log_writer = csv.writer(uam_ped_log_file, delimiter=';')
    uam_ped_log_header = ['timestamp', 'step', 'scenario', 'pedestrianID', 'vehicleID', 'state', 'x', 'y',
                          'routeStartX', 'routeStartY', 'routeDestX', 'routeDestY', 'originalVehicleId', 'uamDensity',
                          'mmDensity', 'uam_vehicles_per_hub', 'uam_vehicle_capacity', 'group_finding_time',
                          'uam_hub_count']
    uam_ped_log_writer.writerow(uam_ped_log_header)

    uam_taxi_log_file_name = "uam-taxi-log-{}.csv".format(os.path.basename(results_folder))
    uam_taxi_log_file_path = os.path.join(results_folder, uam_taxi_log_file_name)
    uam_taxi_log_file = open(uam_taxi_log_file_path, 'w', newline='')

    uam_taxi_log_writer = csv.writer(uam_taxi_log_file, delimiter=';')
    uam_taxi_log_header = ['timestamp', 'step', 'scenario', 'vehicleID', 'state', 'x', 'y', 'pedCount', 'customerIds',
                           'uam_hub_count']
    uam_taxi_log_writer.writerow(uam_taxi_log_header)

    # start of the main simulation loop
    while traci.simulation.getTime() <= config.seconds_to_simulate:
        traci.simulationStep()

        if config.verbosity >= Verbosity.NORMAL:
            print("-----------------------------------------------")
            print("Simulation step: " + str(step))

        peds = set(traci.person.getIDList())
        vehicles = set(traci.vehicle.getIDList())

        # determine terminated vehicles and pedestrians
        terminated_vehicles = last_step_vehicles - vehicles
        terminated_peds = last_step_peds - peds

        terminated_uam_customers = set.intersection(terminated_peds, uam_customers)

        log_terminated_customers(uam_ped_log_writer, step, terminated_uam_customers, uam_log_dict)

        # clean up log dict
        for terminated_uam_customer in terminated_uam_customers:
            if terminated_uam_customer in uam_log_dict:
                del uam_log_dict[terminated_uam_customer]

        uam_customers = uam_customers - terminated_uam_customers

        new_vehicles = vehicles - last_step_vehicles
        new_vehicles -= create_uam_customers(new_vehicles, step, uam_ped_log_writer, uam_customers, uam_log_dict)
        # TODO: create MM customers

        # remove terminated escooters from list of escooters
        escooters = escooters - terminated_vehicles

        find_newly_added_escooters(new_vehicles, escooters)

        # every x seconds look for the best lane for each escooter and change to that
        if step % config.escooter_lane_find_frequency == 0:
            select_escooter_lane(escooters)

        increment_reservation_waiting_time(reservation_dict)
        check_for_new_reservations(reservation_dict, step, uam_ped_log_writer, waiting_peds, uam_log_dict)
        dispatch_uam_vehicles(reservation_dict, parking_area_edges)

        if not config.no_gui:
            if step % 1 == 0:
                recolour_uam_taxis()

        log_taxis(uam_taxi_log_writer, step)

        waiting_peds -= log_started_flights(uam_ped_log_writer, step, waiting_peds, flying_peds, uam_log_dict)
        flying_peds -= log_finished_flights(uam_ped_log_writer, step, flying_peds, uam_log_dict)

        last_step_vehicles = set(vehicles)  # save current vehicles for the next simulation step
        last_step_peds = set(peds)  # save current vehicles for the next simulation step
        step += config.step_length
    traci.close()
    uam_ped_log_file.close()
    uam_taxi_log_file.close()
    sys.stdout.flush()


def generate_start_config(sumo_binary: str, results_folder) -> list[str]:
    """
    Appends all start arguments as defined in simConfig.py and their respective file locations to a list of strings.
    This list is then returned and used to start traci with the appropriate start arguments.

    :param sumo_binary: string with information about the binary (sumo or sumo-gui)
    """
    if options.scenario_path:
        start_config = [sumo_binary, "-c", options.scenario_path]
    else:
        start_config = [sumo_binary, "-c", config.scenarios[config.scenario]]
    if config.loop:
        start_config.append("--start")
        start_config.append("--quit-on-end")
    start_config.append("--device.taxi.dispatch-algorithm")
    start_config.append("traci")
    start_config.append("--device.taxi.idle-algorithm")
    start_config.append("taxistand")
    start_config.append("--lateral-resolution")
    start_config.append(str(config.lateral_resolution))
    start_config.append("--step-length")
    start_config.append(str(config.step_length))
    start_config.append("--gui-settings-file")
    start_config.append(os.path.join("defaultView.xml"))

    if config.outputFilesActive:
        if config.statsOutput:
            start_config.append("--statistic-output")
            start_config.append(os.path.join(results_folder, "stats.xml"))

        if config.tripinfoOutput:
            start_config.append("--tripinfo-output")
            start_config.append(os.path.join(results_folder, "tripinfo.xml"))

        if config.personsummaryOutput:
            start_config.append("--person-summary-output")
            start_config.append(os.path.join(results_folder, "personsummary.xml"))

        if config.summaryOutput:
            start_config.append("--summary")
            start_config.append(os.path.join(results_folder, "summary.xml"))

        if config.vehroutesOutput:
            start_config.append("--vehroute-output")
            start_config.append(os.path.join(results_folder, "vehroutes.xml"))

        if config.fcdOutput:
            start_config.append("--fcd-output")
            start_config.append(os.path.join(results_folder, "fcd.xml"))

        if config.fullOutput:
            start_config.append("--full-output")
            start_config.append(os.path.join(results_folder, "full.xml"))

        if config.queueOutput:
            start_config.append("--queue-output")
            start_config.append(os.path.join(results_folder, "queue.xml"))

        if config.edgedataOutput:
            start_config.append("--edgedata-output")
            start_config.append(os.path.join(results_folder, "edgedata.xml"))

        if config.lanedataOutput:
            start_config.append("--lanedata-output")
            start_config.append(os.path.join(results_folder, "lanedata.xml"))

        if config.lanechangeOutput:
            start_config.append("--lanechange-output")
            start_config.append(os.path.join(results_folder, "lanechange.xml"))

        if config.amitranOutput:
            start_config.append("--amitran-output")
            start_config.append(os.path.join(results_folder, "amitran.xml"))

        if config.ndumpOutput:
            start_config.append("--ndump")
            start_config.append(os.path.join(results_folder, "ndump.xml"))

        if config.linkOutput:
            start_config.append("--link-output")
            start_config.append(os.path.join(results_folder, "link.xml"))

        if config.personinfoOutput:
            start_config.append("--personinfo-output")
            start_config.append(os.path.join(results_folder, "personinfo.xml"))

        if config.emissionOutput:
            start_config.append("--emission-output")
            start_config.append(os.path.join(results_folder, "emission.xml"))

    return start_config


def generate_base_results_folder(path: str):
    scenario_filename = os.path.basename(path)
    scenario_name = scenario_filename[11:-8]  # this assumes that the .sumocfg has "x_uam_hubs_" as prefix
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder_name = str(scenario_filename[0]) + "_hubs_" + scenario_name + "_" + str(timestamp)
    config.results_folder_path = os.path.join(config.results_folder_path, folder_name)


# creates new folder for results in next simulation
def get_new_results_folder():
    data_output_path = os.path.join(config.results_folder_path,
                                    "{}-uam{:.3f}-mm{:.3f}-{}".format(config.scenario, config.uam_density,
                                                                      config.mm_density,
                                                                      datetime.now().strftime("%Y%m%d-%H%M%S")))

    if not os.path.exists(data_output_path):
        os.makedirs(data_output_path)
        return data_output_path
    else:
        return ""


def process_options():
    if options.verbosity is not None:
        match options.verbosity:
            case "none":
                config.verbosity = Verbosity.NONE
            case "sparse":
                config.verbosity = Verbosity.SPARSE
            case "normal":
                config.verbosity = Verbosity.NORMAL
            case "verbose":
                config.verbosity = Verbosity.VERBOSE
    if options.time_steps is not None:
        config.seconds_to_simulate = options.time_steps
    if options.step_length is not None:
        config.step_length = options.step_length
    if options.loop is not None:
        config.loop = options.loop
    if options.uam_vehicles_per_hub is not None:
        config.uam_vehicles_per_hub = options.uam_vehicles_per_hub
    if options.uam_vehicle_capacity is not None:
        config.uam_vehicle_capacity = options.uam_vehicle_capacity
    if options.group_finding_time is not None:
        config.group_finding_time = options.group_finding_time
    if options.lateral_resolution is not None:
        config.lateral_resolution = options.lateral_resolution
    if options.uam_upper_bound is not None:
        config.uam_upper_bound = options.uam_upper_bound
    if options.mm_upper_bound is not None:
        config.mm_upper_bound = options.mm_upper_bound
    if options.uam_step_size is not None:
        config.uam_step_size = options.uam_step_size
    if options.mm_step_size is not None:
        config.mm_step_size = options.mm_step_size
    if options.uam_start_density is not None:
        config.uam_density = options.uam_start_density
        config.uam_start_density = options.uam_start_density
    if options.mm_start_density is not None:
        config.mm_density = options.mm_start_density
        config.mm_start_density = options.mm_start_density
    if options.nogui is not None:
        config.no_gui = options.nogui
    if options.scenario is not None:
        config.scenario = options.scenario
    if options.scenario_path is not None:
        config.scenario = "custom"


if __name__ == '__main__':

    options = get_options()
    process_options()
    if config.scenario == "custom":
        net_path = os.path.join(os.path.dirname(options.scenario_path), ET.parse(options.scenario_path).getroot().find(
            ".//net-file").get("value").split("/")[0])
        scenario_path = options.scenario_path
    else:
        net_path = os.path.join(os.path.dirname(config.scenarios[config.scenario]),
                                ET.parse(config.scenarios[config.scenario]).getroot().find(
                                    ".//net-file").get("value").split("/")[0])
        scenario_path = config.scenarios[config.scenario]

    net = sumolib.net.readNet(net_path)

    # check binary
    if config.no_gui:
        sumoBinary = checkBinary('sumo')
        config.no_gui = True
    else:
        sumoBinary = checkBinary('sumo-gui')
        config.no_gui = False

    generate_base_results_folder(scenario_path)

    if not config.loop:  # run simulation once
        results_folder = get_new_results_folder()
        traci_start_config = generate_start_config(sumoBinary, results_folder)
        # traci starts sumo as a subprocess and then this script connects and runs
        traci.start(traci_start_config)
        run()
    else:  # run multiple simulations in a row, looping through uam and mm density
        while config.mm_density <= config.mm_upper_bound:
            while config.uam_density <= config.uam_upper_bound:
                print("uam_density: " + str(config.uam_density) + ", mm_density: " + str(
                    config.mm_density) + ", uam_upper_bound: " + str(
                    config.uam_upper_bound) + ", mm_upper_bound: " + str(
                    config.mm_upper_bound) + ", uam_step_size: " + str(config.uam_step_size) + ", mm_step_size: " + str(
                    config.mm_step_size))
                if config.uam_density + config.mm_density > 1.0:  # we can't convert over 100% of vehicles to alternatives
                    break
                results_folder = get_new_results_folder()
                traci_start_config = generate_start_config(sumoBinary, results_folder)
                # traci starts sumo as a subprocess and then this script connects and runs
                traci.start(traci_start_config)
                run()
                if config.uam_step_size == 0.0:
                    break
                config.uam_density += config.uam_step_size
            config.uam_density = config.uam_start_density
            if config.mm_step_size == 0.0:
                break
            config.mm_density += config.mm_step_size
