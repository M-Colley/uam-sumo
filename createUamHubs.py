import argparse
import os
import subprocess
import xml.etree.ElementTree as ET
import math
import uamHubConfig as config
# import numpy as np

import sumolib


def get_options():
    """
    Command line options using the argparse library
    """
    parser = argparse.ArgumentParser(description="Process some coordinates.")
    parser.add_argument('file_path', type=str, help='Path to the sumocfg file.')
    parser.add_argument('coordinates', type=float, nargs='+',
                        help="The coordinates for the uam hub locations, always pass x first, followed by y. Repeat any number of times. "
                             "Example: passing 1 2 3 4 5 6 creates [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)].")
    args = parser.parse_args()
    return args


def get_centre(coordinates: list[(float, float)]) -> (float, float):
    xs = [p[0] for p in coordinates]
    ys = [p[1] for p in coordinates]
    centre = (sum(xs) / len(coordinates), sum(ys) / len(coordinates))

    return centre


def get_orthogonal_points(centre: (float, float), point: (float, float), distance: float) -> (
(float, float), (float, float)):
    # calculate the direction vector from centre to point
    dx = point[0] - centre[0]
    dy = point[1] - centre[1]

    # normalize the direction vector
    length = math.sqrt(dx ** 2 + dy ** 2)
    dx /= length
    dy /= length

    # calculate the orthogonal vector
    orthogonal_dx = -dy
    orthogonal_dy = dx

    # calculate the two new points
    point1 = (point[0] - orthogonal_dx * distance, point[1] - orthogonal_dy * distance)
    point2 = (point[0] + orthogonal_dx * distance, point[1] + orthogonal_dy * distance)

    return point1, point2


def generate_junctions(net_file, coordinates: list[(float, float)], out_net_file) -> list[str]:
    tree = ET.parse(net_file)
    root = tree.getroot()
    centre = get_centre(coordinates)
    hub_count = 0
    junction_ids = list()
    for hub_location in coordinates:
        orthogonals = get_orthogonal_points(centre, hub_location, config.uam_hub_length / 2)
        hub_junction_count = 0
        for point in orthogonals:
            new_id = "uam_hub_junction_" + str(hub_count) + "_" + str(hub_junction_count)
            root.append(ET.Element('junction', {
                'id': new_id,
                'x': str(point[0]),
                'y': str(point[1]),
                'type': 'priority',
            }))
            junction_ids.append(new_id)
            print("creating new junction: \"" + new_id + "\" at x = " + str(point[0]) + ", y = " + str(point[1]))
            hub_junction_count += 1
        hub_count += 1

    tree.write(out_net_file)
    return junction_ids


def generate_edges(root, junction_ids: list[str]):
    for index in range(0, len(junction_ids), 2):
        edge_id = "uam_edge_" + str(index) + "_" + str(index + 1)
        new_edge = ET.Element('edge', {
            'id': edge_id,
            'from': junction_ids[index],
            'to': junction_ids[index + 1],
            'priority': '-1'
        })
        print("creating new edge: \"" + edge_id + "\" from " + str(junction_ids[index]) + " to = " + junction_ids[index + 1])
        #lane_id = edge_id + "_0"
        #new_lane = ET.SubElement(new_edge, 'lane', {
        #    'id': lane_id,
        #    'index': '0',
        #    'speed': '13.89',
        #    'width': '2.0',
        #    'allow': 'taxi'})
        #print("creating new lane for edge.")
        root.append(new_edge)


def connect_junctions(net_file, junction_ids, out_file_path, edge_coord_dict, coordinates) -> list[str]:
    """
    Chunks of this function have been taken from Jakob Erdmann's buildFullGraph.py, authored 2024-05-02
    """
    prefix = net_file
    if prefix.endswith(".net.xml.gz"):
        prefix = prefix[:-11]
    elif prefix.endswith(".net.xml"):
        prefix = prefix[:-8]

    edge_patch = prefix + ".patch.edg.xml"

    edge_ids = list()

    with open(edge_patch, 'w') as outfe:
        sumolib.writeXMLHeader(outfe, "$Id$", "edges")
        for index in range(0, len(junction_ids), 2):
            new_edge_id = "uam_%s_%s" % (index, index + 1)
            outfe.write(
                '    <edge id="%s" from="%s" to="%s" speed="%s" numLanes="%s" width="%s" allow="%s"/>\n' % (  # noqa
                    new_edge_id, junction_ids[index], junction_ids[index + 1],
                    config.uam_hub_edge_speed, 1, config.uam_hub_edge_width, "taxi pedestrian"))
            print("creating new edge: \"" + new_edge_id + "\" from " + str(junction_ids[index]) + " to " + junction_ids[
                index + 1])
            edge_ids.append(new_edge_id)
            edge_coord_dict[new_edge_id] = coordinates[int(index / 2)]

        outfe.write("</edges>\n")

    NETCONVERT = sumolib.checkBinary('netconvert')
    subprocess.call([NETCONVERT,
                     '-s', net_file,
                     '-e', edge_patch,
                     '-o', out_file_path])
    return edge_ids


def generate_additionals(edges: list[str], add_file, net_file, out_add_file, coordinates: list[(float, float)], pa_edge_ids):
    tree = ET.parse(add_file)
    root = tree.getroot()
    edge_count = 0
    pa_ids = list()
    net = sumolib.net.readNet(net_file)
    for edge in edges:
        edge_length = net.getEdge(edge).getLength()
        bus_stop_id = "uam_hub_stop_" + str(edge_count)
        parking_area_id = "uam_parking_area" + str(edge_count)
        #new_pa_start_pos = edge_length / 4 - config.parking_area_length / 2
        new_pa_start_pos = 20
        #new_bs_start_pos = 3 * edge_length / 4 - config.bus_stop_length / 2
        new_bs_start_pos = 20
        pa_start_pos = config.uam_hub_length / 2 + 1

        closest_edge_with_sidewalk = find_closest_sidewalk(coordinates[edge_count], net_file)
        if closest_edge_with_sidewalk == "":
            print("couldn't generate uam hub, skipping to next.")
            edge_count += 1
            continue

        if edge_count == 0:
            fake_pa = ET.Element('parkingArea', {
                'id': config.fake_parking_area_id,
                'lane': edge + "_0",
                'startPos': "0",
                'endPos': "10",
                'roadsideCapacity': "0"
            })
            pa_ids.append(config.fake_parking_area_id)
            root.append(fake_pa)

        new_pa = ET.Element('parkingArea', {
            'id': parking_area_id,
            'lane': "-" + edge + "_0",
            'startPos': str(new_pa_start_pos),
            'endPos': str(new_pa_start_pos + config.parking_area_length),
            'roadsideCapacity': str(config.uam_pa_capacity)
        })
        print("creating new parking area : \"" + parking_area_id + "\" for edge " + edge)
        pa_ids.append(parking_area_id)
        '''
        new_stop = ET.Element('busStop', {
            'id': bus_stop_id,
            'lane': edge + "_0",                                # uam lane should only have 1 lane
            'startPos': str(pa_start_pos + config.parking_area_length + 1),
            'endPos': str(pa_start_pos + config.parking_area_length + 1 + config.bus_stop_length)
        })
        '''
        new_stop = ET.Element('busStop', {
            'id': bus_stop_id,
            'lane': edge + "_0",  # uam lane should only have 1 lane
            'startPos': str(new_bs_start_pos),
            'endPos': str(new_bs_start_pos + config.bus_stop_length)
        })
        print("creating new parking bus stop : \"" + bus_stop_id + "\" for edge " + edge)

        ET.SubElement(new_stop, 'access', {
            'lane': closest_edge_with_sidewalk + "_0",
            'pos': "0"                                          # TODO: optimize
        })
        print("creating access point for \"" + bus_stop_id + "\": connecting with edge: \"" + closest_edge_with_sidewalk + "\"")

        root.append(new_pa)
        root.append(new_stop)
        edge_count += 1

    rerouter_element_edges = pa_edge_ids + edges

    rerouter = ET.Element('rerouter', {
        'id': config.rerouter_id,
        'edges': " ".join(rerouter_element_edges)
    })
    interval = ET.SubElement(rerouter, 'interval', {
        'begin': "0.00",
        'end': str(config.rerouter_end_time)
    })
    for pa_id in pa_ids:
        ET.SubElement(interval, 'parkingAreaReroute', {
            'id': pa_id,
            'visible': "1"
        })
    root.append(rerouter)
    print("creating uam taxi rerouter \"" + config.rerouter_id + "\"")

    tree.write(out_add_file)


def find_closest_sidewalk(point: (float, float), net_file) -> str:
    net = sumolib.net.readNet(net_file)
    for i in range(1, 10):
        nearby_edges = net.getNeighboringEdges(point[0], point[1],
                                               config.sidewalk_search_radius * i, includeJunctions=False)
        if len(nearby_edges) > 0:
            nearby_edges_sorted = sorted([(dist, edge) for edge, dist in nearby_edges], key=lambda x: x[0])
            for nearby_edge in nearby_edges_sorted:
                edge_id = nearby_edge[1].getID()
                if nearby_edge[1].allows("pedestrian"):
                    if "uam" not in edge_id:    # avoid pointing to uam lane
                        return edge_id
        if i == 9:
            print("No nearby sidewalk could be found, aborting creation of access points.")
            return ""


'''
def calculate_optimal_access_point_distance(from_coord, to_coord, point):
    A = np.array(from_coord)
    B = np.array(to_coord)
    P = np.array(point)

    AB = B - A
    AP = P - A

    AB_AB = np.dot(AB, AB)
    AP_AB = np.dot(AP, AB)

    t = AP_AB / AB_AB

    if t < 0.0:
        closest_point = A
    elif t > 1.0:
        closest_point = B
    else:
        closest_point = A + t * AB

    # Calculate the distance from to_coord to the closest point
    distance = np.linalg.norm(closest_point - B)

    return distance
'''


def disallow_taxis(net_file, out_net_file):
    sumo_home = os.environ.get('SUMO_HOME')
    if sumo_home is None:
        raise EnvironmentError("SUMO_HOME environment variable is not set.")

    subprocess.call(["python",
                     f"{sumo_home}/tools/net/patchVClasses.py",
                     net_file,
                     "--disallow", "taxi",
                     "-o", out_net_file])
    print("disallowed taxis on all edges of the network")


def add_uam_taxi_vclass(route_file, out_route_file):
    tree = ET.parse(route_file)
    root = tree.getroot()
    uam_taxi = ET.Element('vType', {    # TODO: width, height, length
        'id': "uamtaxi",
        'vClass': "taxi",
        'guiShape': "aircraft",
        'personCapacity': str(config.uam_taxi_person_capacity),
        'maxSpeed': str(config.uam_taxi_max_speed),
        'emissionClass': "Energy/unknown"
    })
    ET.SubElement(uam_taxi, 'param', {
        'key': "device.taxi.stands-rerouter",
        'value': config.rerouter_id
    })
    ET.SubElement(uam_taxi, 'param', {
        'key': "has.taxi.device",
        'value': "true"
    })
    ET.SubElement(uam_taxi, 'param', {
        'key': "parking.absfreespace.weight",
        'value': str(config.taxi_abs_free_space_weight)
    })
    ET.SubElement(uam_taxi, 'param', {
        'key': "parking.distanceto.weight",
        'value': str(config.taxi_distance_to_weight)
    })
    ET.SubElement(uam_taxi, 'param', {
        'key': "parking.timeto.weight",
        'value': str(config.taxi_time_to_weight)
    })
    ET.SubElement(uam_taxi, 'param', {
        'key': "parking.relfreespace.weight",
        'value': str(config.taxi_rel_free_space_weight)
    })
    ET.SubElement(uam_taxi, 'param', {
        'key': "device.taxi.pickUpDuration",
        'value': str(config.uam_pick_up_duration)
    })
    ET.SubElement(uam_taxi, 'param', {
        'key': "device.taxi.dropOffDuration",
        'value': str(config.uam_drop_off_duration)
    })
    print("adding new vehicle type \"uamtaxi\"")
    root.insert(0, uam_taxi)
    tree.write(out_route_file)


def connect_hubs(net_file, out_net_file, edge_coord_dict):
    """
    Chunks of this function have been taken from Jakob Erdmann's buildFullGraph.py, authored 2024-05-02
    """
    net = sumolib.net.readNet(net_file)
    base_edges = [e for e in net.getEdges() if e.allows("taxi") and "uam" in e.getID()]
    prefix = net_file
    if prefix.endswith(".net.xml.gz"):
        prefix = prefix[:-11]
    elif prefix.endswith(".net.xml"):
        prefix = prefix[:-8]

    edge_patch = prefix + ".patch.edg.xml"
    con_patch = prefix + ".patch.con.xml"
    with open(edge_patch, 'w') as outfe, open(con_patch, 'w') as outfc:
        sumolib.writeXMLHeader(outfe, "$Id$", "edges")
        sumolib.writeXMLHeader(outfc, "$Id$", "connections")
        for e1 in base_edges:
            for e2 in base_edges:
                if e1 != e2 and e2 not in e1.getOutgoing():
                    if not in_radius(edge_coord_dict[e1.getID()], edge_coord_dict[e2.getID()]):
                        continue
                    new_eid = "%s_%s" % (e1.getToNode().getID(), e2.getFromNode().getID())
                    width = config.uam_con_edge_width if config.uam_con_edge_width is not None else e1.getLanes()[-1].getWidth()
                    outfe.write('    <edge id="%s" from="%s" to="%s" speed="%s" numLanes="%s" width="%s" allow="%s"/>\n' % (  # noqa
                        new_eid, e1.getToNode().getID(), e2.getFromNode().getID(),
                        config.uam_con_edge_speed, 1, width, "taxi"))
                    print("creating edge from \"" + e1.getToNode().getID() + "\" to \"" + e2.getFromNode().getID() + "\"")
                    outfc.write('    <connection from="%s" to="%s" fromLane="0" toLane="0"/>\n' % (e1.getID(), new_eid))
                    print("creating connection from \"" + e1.getID() + "\" to \"" + new_eid + "\"")
                    outfc.write('    <connection from="%s" to="%s" fromLane="0" toLane="0"/>\n' % (new_eid, e2.getID()))
                    print("creating connection from \"" + new_eid + "\" to \"" + e2.getID() + "\"")

        outfe.write("</edges>\n")
        outfc.write("</connections>\n")

    NETCONVERT = sumolib.checkBinary('netconvert')
    subprocess.call([NETCONVERT,
                     '-s', net_file,
                     '-e', edge_patch,
                     '-x', con_patch,
                     '-o', out_net_file])


def in_radius(point1: (float, float), point2: (float, float)) -> bool:
    if math.dist(point1, point2) <= config.uam_hub_connection_radius:
        return True
    else:
        return False


def create_reverse_directions(net_file, out_net_file, junction_ids):
    """
    Chunks of this function have been taken from Jakob Erdmann's buildFullGraph.py, authored 2024-05-02
    """
    prefix = net_file
    if prefix.endswith(".net.xml.gz"):
        prefix = prefix[:-11]
    elif prefix.endswith(".net.xml"):
        prefix = prefix[:-8]

    edge_patch = prefix + ".patch.edg.xml"
    con_patch = prefix + ".patch.con.xml"

    reverse_edge_ids = list()

    with open(edge_patch, 'w') as outfe, open(con_patch, 'w') as outfc:
        sumolib.writeXMLHeader(outfe, "$Id$", "edges")
        sumolib.writeXMLHeader(outfc, "$Id$", "connections")
        for index in range(0, len(junction_ids), 2):
            edge_id = "uam_%s_%s" % (index, index + 1)
            reverse_edge_id = "-" + edge_id
            outfe.write(
                '    <edge id="%s" from="%s" to="%s" speed="%s" numLanes="%s" width="%s" allow="%s"/>\n' % (  # noqa
                    reverse_edge_id, junction_ids[index + 1], junction_ids[index],
                    config.uam_hub_edge_speed, 1, config.uam_con_edge_width, "taxi"))
            print("creating edge from \"" + junction_ids[index + 1] + "\" to \"" + junction_ids[index] + "\"")
            outfc.write('    <connection from="%s" to="%s" fromLane="0" toLane="0"/>\n' % (reverse_edge_id, edge_id))
            print("creating connection from \"" + reverse_edge_id + "\" to \"" + edge_id + "\"")
            outfc.write('    <connection from="%s" to="%s" fromLane="0" toLane="0"/>\n' % (edge_id, reverse_edge_id))
            print("creating connection from \"" + edge_id + "\" to \"" + reverse_edge_id + "\"")

            reverse_edge_ids.append(reverse_edge_id)

        outfe.write("</edges>\n")
        outfc.write("</connections>\n")

    NETCONVERT = sumolib.checkBinary('netconvert')
    subprocess.call([NETCONVERT,
                     '-s', net_file,
                     '-e', edge_patch,
                     '-x', con_patch,
                     '-o', out_net_file])
    return reverse_edge_ids


def create_new_sumocfg(sumocfg_file, net_file, rou_files, add_files, hub_count):
    tree = ET.parse(sumocfg_file)
    root = tree.getroot()

    root.find('.//net-file').set('value', net_file)
    root.find('.//route-files').set('value', ",".join(rou_files))
    root.find('.//additional-files').set('value', ",".join(add_files))
    # root.find('.//additional-files').set('value', ",".join(add_files))
    # root.find('.//additional-files').set('value', add_files)

    tree.write(os.path.join(os.path.dirname(sumocfg_file), str(hub_count) + "_uam_hubs_" + str(os.path.basename(sumocfg_file))))


def connect_to_network(net_file, out_file_path, junction_ids, coordinates):

    # as of 20.08.2024, there is a problem with routing using access elements
    # temporary fix: add pedestrian lanes to road network to allow routing to UAM network

    net = sumolib.net.readNet(net_file)

    prefix = net_file
    if prefix.endswith(".net.xml.gz"):
        prefix = prefix[:-11]
    elif prefix.endswith(".net.xml"):
        prefix = prefix[:-8]

    edge_patch = prefix + ".patch.edg.xml"

    with open(edge_patch, 'w') as outfe:
        sumolib.writeXMLHeader(outfe, "$Id$", "edges")
        for index in range(0, len(junction_ids), 2):

            for i in range(1, 10):
                nearby_edges = net.getNeighboringEdges(coordinates[int(index / 2)][0], coordinates[int(index / 2)][1],
                                                       config.sidewalk_search_radius * i, includeJunctions=False)
                if len(nearby_edges) > 0:
                    nearby_edges_sorted = sorted([(dist, edge) for edge, dist in nearby_edges], key=lambda x: x[0])
                    for nearby_edge in nearby_edges_sorted:
                        edge_id = nearby_edge[1].getID()
                        if nearby_edge[1].allows("pedestrian"):
                            if "uam" not in edge_id:  # avoid pointing to uam lane
                                from_junction_id = net.getEdge(edge_id).getFromNode().getID()
                                temp_edge_id = "hub_con_%s_%s" % (index, from_junction_id)
                                outfe.write(
                                    '    <edge id="%s" from="%s" to="%s" speed="%s" numLanes="%s" width="%s" allow="%s"/>\n' % (
                                        # noqa
                                        temp_edge_id, from_junction_id, junction_ids[index],
                                        100 / 3.6, 1, 2, "pedestrian"))
                                print(
                                    "creating new edge: \"" + temp_edge_id + "\" from " + str(junction_ids[index]) + " to " +
                                    from_junction_id)
                                break
                    else:
                        continue
                    break
                if i == 9:
                    print("No nearby sidewalk could be found, aborting creation of access fix.")

        outfe.write("</edges>\n")

    NETCONVERT = sumolib.checkBinary('netconvert')
    subprocess.call([NETCONVERT,
                     '-s', net_file,
                     '-e', edge_patch,
                     '-o', out_file_path])


def generate_hubs(coordinates: list[(float, float)]):
    sumocfg_path = os.path.normpath(options.file_path)
    sumocfg_dir_path = os.path.dirname(sumocfg_path)
    net_path = os.path.join(os.path.dirname(sumocfg_path),
                            ET.parse(sumocfg_path).getroot().find(".//net-file").get("value").split("/")[0])
    net_file = ET.parse(sumocfg_path).getroot().find(".//net-file").get("value").split("/")[0]
    route_files = ET.parse(sumocfg_path).getroot().find(".//route-files").get("value").split("/")[0].split(",")
    add_files = ET.parse(sumocfg_path).getroot().find(".//additional-files").get("value").split("/")[0].split(",")

    route_path = os.path.join(os.path.dirname(sumocfg_path), route_files[0])    # TODO: maybe we want another route file?
    add_path = os.path.join(os.path.dirname(sumocfg_path), add_files[0])

    if not (os.path.isfile(sumocfg_path)):
        print("Not a valid sumocfg path.")
        return
    if not (os.path.isfile(os.path.join(sumocfg_dir_path, net_file))):
        print("Not a valid net path.")
        return
    if not (os.path.isfile(os.path.join(sumocfg_dir_path, route_files[0]))):
        print("Not a valid route path.")
        return
    if not (os.path.isfile(os.path.join(sumocfg_dir_path, add_files[0]))):
        print("Not a valid additionals path.")
        return

    edge_coord_dict = dict()

    original_net_path = net_path

    #new_dir_path = os.path.join(sumocfg_dir_path, "uamHubs")

    #if not os.path.exists(new_dir_path):
    #    os.makedirs(new_dir_path)
    test_net_path = os.path.join(sumocfg_dir_path, str(int(len(coordinates))) + "_uam_hubs_" + str(os.path.basename(net_path)))
    test_rou_path = os.path.join(sumocfg_dir_path, str(int(len(coordinates))) + "_uam_hubs_" + str(os.path.basename(route_path)))
    test_add_path = os.path.join(sumocfg_dir_path, str(int(len(coordinates))) + "_uam_hubs_" + str(os.path.basename(add_path)))

    new_net_path = os.path.join(os.path.dirname(net_path), "no_taxis_" + str(os.path.basename(net_path)))
    #disallow_taxis(net_path, new_net_path)
    disallow_taxis(net_path, test_net_path)
    net_path = new_net_path

    new_net_path = os.path.join(os.path.dirname(net_path), "added_junctions_" + str(os.path.basename(net_path)))
    #junction_ids = generate_junctions(net_path, coordinates, new_net_path)
    junction_ids = generate_junctions(test_net_path, coordinates, test_net_path)
    net_path = new_net_path

    new_net_path = os.path.join(os.path.dirname(net_path), "added_hub_edges_" + str(os.path.basename(net_path)))
    #new_edges = connect_junctions(net_path, junction_ids, new_net_path, edge_coord_dict, coordinates)
    new_edges = connect_junctions(test_net_path, junction_ids, test_net_path, edge_coord_dict, coordinates)
    net_path = new_net_path

    new_net_path = os.path.join(os.path.dirname(net_path), "added_hub_connections_" + str(os.path.basename(net_path)))
    connect_hubs(test_net_path, test_net_path, edge_coord_dict)
    # connect_hubs(net_path, new_net_path, edge_coord_dict)
    net_path = new_net_path

    new_net_path = os.path.join(os.path.dirname(original_net_path), "uam_" + str(os.path.basename(original_net_path)))
    pa_edge_ids = create_reverse_directions(test_net_path, test_net_path, junction_ids)
    #create_reverse_directions(net_path, new_net_path, junction_ids)

    new_add_path = os.path.join(os.path.dirname(net_path), "added_additionals_" + str(os.path.basename(add_path)))
    #generate_additionals(new_edges, add_path, test_net_path, new_add_path, coordinates)
    generate_additionals(new_edges, add_path, test_net_path, test_add_path, coordinates, pa_edge_ids)

    # temporary fix because of access element routing problem
    net_path = new_net_path
    new_net_path = os.path.join(os.path.dirname(original_net_path), "fixed_uam_" + str(os.path.basename(original_net_path)))
    #connect_to_network(net_path, new_net_path, junction_ids, coordinates)
    connect_to_network(test_net_path, test_net_path, junction_ids, coordinates)

    new_route_path = os.path.join(os.path.dirname(route_path), "modified_" + str(os.path.basename(route_path)))
    #add_uam_taxi_vclass(route_path, new_route_path)
    add_uam_taxi_vclass(route_path, test_rou_path)

    #route_files[0] = os.path.basename(new_route_path)
    route_files[0] = os.path.basename(test_rou_path)
    #add_files[0] = os.path.basename(new_add_path)
    add_files[0] = os.path.basename(test_add_path)
    #create_new_sumocfg(sumocfg_path, os.path.basename(new_net_path), route_files, add_files)
    create_new_sumocfg(sumocfg_path, os.path.basename(test_net_path), route_files, add_files, int(len(coordinates)))


def main():
    # Ensure we have pairs of coordinates
    if len(options.coordinates) % 2 != 0:
        print("Please provide an even number of coordinates.")
        return

    # Process the coordinates
    coordinates = [(options.coordinates[i], options.coordinates[i + 1]) for i in range(0, len(options.coordinates), 2)]
    print("Coordinates:", coordinates)
    generate_hubs(coordinates)


if __name__ == "__main__":
    options = get_options()
    main()
