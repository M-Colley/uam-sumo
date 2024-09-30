#!/usr/bin/env python

#--- uam hub variables ---#
uam_hub_length = 80                 # length of uam hub lane in meters
uam_hub_edge_width = 2              # width of uam hub lane in meters
uam_hub_edge_speed = 200 / 3.6      # allowed max speed on uam hub lane in m/s
uam_con_edge_width = 2              # width in meters of lane connecting uam hubs
uam_con_edge_speed = 200 / 3.6      # allowed max speed on uam hub connection lanes in m/s
parking_area_length = 10            # length of uam hub parking area in meters
bus_stop_length = 10                # length of uam hub bus stop in meters
uam_pa_capacity = 10                # number of parking spaces on each uam hub parking area
sidewalk_search_radius = 300        # initial sidewalk search radius in meters around uam hub. Up to 10x this range is searched before aborting the search
uam_hub_connection_radius = 20000   # maximum distance in meters each pair of uam hubs can be apart from one another to create a direct connection between them

#--- Air Taxi parameters ---#
uam_taxi_person_capacity = 4        # maximum number of passengers in the Air Taxi
uam_taxi_max_speed = 180 / 3.6      # maximum speed of Air Taxi in m/s
uam_taxi_length = 9.2               # length of Air Taxi in meters TODO
uam_taxi_width = 9.2                # width of Air Taxi in meters TODO
uam_taxi_height = 3                 # height of Air Taxi in meters TODO
uam_drop_off_duration = 60          # time in seconds the Air Taxi takes to drop of the customers after arriving at the destination
uam_pick_up_duration = 60           # time in seconds the Air Taxi takes to pick up the customers before starting the flight, after the Air Taxi reaches the customer

#--- Air Taxi parking area finding weights ---#
taxi_abs_free_space_weight = 0      # weight for absolute number of free parking area spaces
taxi_distance_to_weight = 10        # weight for the distance of Air Taxi to parking area
taxi_time_to_weight = 0             # weight for estimated travel time of Air Taxi to parking area
taxi_rel_free_space_weight = 100    # weight for relative number of free parking area spaces to maximum number of parking spaces at parking area

#--- parking area rerouter settings ---#
rerouter_id = "uam_parking_rerouter"
rerouter_end_time = 360000.00
fake_parking_area_id = "empty_rerouter_parking_area"


