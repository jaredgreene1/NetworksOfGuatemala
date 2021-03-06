import csv
import itertools
import math
import pickle
import decimal


def get_signal_loss(freq, dist):
    ##freq in Mhz and dist in miles
    ##equation source: http://www.l-com.com/content/Wireless-Calculators.html
    ##(Free Space Loss Wireless Calculator - Power loss over distance)
    return 36.56 + (20 * math.log10(freq)) + (20 * math.log10(dist))


def get_distance_approximation(freq, desired_signal):
    
    ##the function works by taking the maximum possible distance value that the
    ##formula in get_signal_loss accepts and decreasing this value until it results
    ##in a signal_loss less than the desired_signal and then oscillating the distance
    ##with increasingly smaller values until it hones in on the distance value that
    ##results in the desired_signal
    
    if desired_signal < 0:
        desired_signal = 0
    dist = Decimal(100)
    ##max value possible for distance
    dist_change_factor = 0.1
    ##the factor used for determining how much to change distance by
    change_add_index = True
    ##used for determining whether to change the index of prev_two_adds
    increase_power = 0
    ##the amount by which to increase the power by which dist is reduced by
    signal_loss = Decimal(100000)
    ##default value
    prev_two_adds = [False, True]
    ##used for when signal_loss is oscillating around desired_signal as it
    ##helps determine when to add to increase_power
    while math.fabs(signal_loss) > 0.00000000000000001 + desired_signal:
        ##small amount added to prevent desired_signal from possibly equaling zero
        signal_loss = Decimal(get_signal_loss(freq, dist))
        ##gets the signal loss for freq and current dist value
        add = False
        if signal_loss < desired_signal:
            ##if the signal_loss is less than the desired_signal then add to
            ##distance to increase signal_loss in the next iteration of the loop
            add = True
        cont = True
        power = 0
        while cont:
            if dist <= Decimal(dist_change_factor) / Decimal(math.pow(10, power)):
                ##determine by how much dist can be reduced
                ##ex. if dist = 15.4, then it will reduce dist by 0.1; if dist = 0.35,
                ##then it will reduce dist by 0.01
                power += 1
            else:
                cont = False
        increase_power += 1 if add == prev_two_adds[1] and add != prev_two_adds[0] else 0
        ##if signal_loss is oscillating around desired_signal, then increase the
        ##amount by which dist will be reduced
        amount_to_change = Decimal(dist_change_factor) / Decimal(math.pow(10, power + increase_power))
        ##determine by amount that dist will change by
        dist += amount_to_change if add is True else amount_to_change * -1
        ##add or subtract from dist depending on if signal_loss is
        ##less than or greater than desired_signal
        if change_add_index == True:
            prev_two_adds[0] = add
        else:
            prev_two_adds[1] = add
    return dist.quantize(Decimal('1.000000000000000000000000')), signal_loss
    ##returns the distance for which signal_loss is very close in value to desired_signal


def convert_miles_to_km(distance):
    return distance * 1.609344


def open_csv(name):
    with open(name) as f:
        reader = csv.reader(f)
        data = list(reader)
    data = data[1:]
    ##remove column names
    return data


def clean_tigo_data(data):
    ##remove incomplete data
    invalids = set(['TBD', 'NA'])
    return filter(lambda (cell, lat, lon): set([lat, lon]).isdisjoint(invalids), data)


def clean_open_cell_id_data(data):
    ##remove non-tigo data
    tigo_id = data[2]
    return filter(lambda (a, b, c, d, e, f, g): c == tigo_id, data)


def get_columns(data, cols):
    ##cols should be a list of the indices of the columns wanted from data
    mod_data = list()
    for x in data:
        holder = list()
        for col in cols:
            holder.append(x[col])
        mod_data.append(holder)
    return mod_data


def distance_between_coords(lat1, lon1, lat2, lon2):
    ##source: http://en.wikipedia.org/wiki/Lat-lon
    lat_mid = (lat1 + lat2) / 2
    lon_mid = (lon1 + lon2) / 2
    m_per_deg_lat = 111132.954 - 559.822 * math.cos(2 * lat_mid) + 1.175 * math.cos(4 * lat_mid)
    m_per_deg_lon = (3.14159265359 / 180) * 6367449 * math.cos(lat_mid)
    delta_lat = math.fabs(lat1 - lat2)
    delta_lon = math.fabs(lon1 - lon2)
    return math.sqrt((delta_lat * m_per_deg_lat)**2 + (delta_lon * m_per_deg_lon)** 2)


def long_cid_to_short_cid(long_cid):
    ##modulus reduction to get last 16 bits from long_cid to make the short_cid
    return long_cid % (2**16)


def num_to_bin(num):
    ##return binary representation of number
    return bin(int(num))


def num_to_bin_str(num):
    ##return the binary representation of a number (split up by groups of four
    ##bits for readability)
    binary_str = str(bin(int(num)))[2:]
    mod_str = ""
    for x in range(0, len(binary_str)):
        if (x + 1) % 5 == 0:
            mod_str += " "
        else:
            mod_str += binary_str[x]
    return mod_str


def put_cell_id_together(cell):
    #puts together open_cell_id data into tigo's format for cell_ids
    short_cid = str(long_cid_to_short_cid(int(cell[4])))
    return cell[1] + '0' + cell[2] + cell[3] + short_cid


def get_cells_in_area(open_cell_id_data):
    ##makes a dictionary where the key is the area number and the value
    ##is another dictionary where the keys are lte/gsm/umts
    ##and the values are lists of the cells in that area with that technology
    areas = dict()
    for cell in open_cell_id_data:
        cell.append(put_cell_id_together(cell))
        if cell[3] not in areas.keys():
            areas[cell[3]] = {cell[0]: [cell]}
        else:
            cells_in_area = areas[cell[3]]
            if cell[0] in cells_in_area.keys():
                cell_data = cells_in_area[cell[0]]
                cell_data.append(cell)
                cells_in_area[cell[0]] = cell_data
            else:
                cells_in_area[cell[0]] = [cell]
            areas[cell[3]] = cells_in_area
    return areas


def match_tigo_data(tigo, open_cell_id_areas):
    ##makes a dictionary where the key is the area number and the
    ##value is another dictionary where the keys are lte/gsm/umts
    ##and the values are lists of the cells in that area with that
    ##technology that also exist in open_cell_id
    tigo_match_data = dict()
    tigo_cell_ids = [element[0] for element in tigo]
    for area in open_cell_id_areas.keys():
        cells = dict()
        for tech in open_cell_id_areas[area].keys():
            tech_dict = open_cell_id_areas[area][tech]
            for cell in open_cell_id_areas[area][tech]:
                if cell[7] in tigo_cell_ids:
                    if tech not in cells.keys():
                        cells[tech] = [cell]
                    else:
                        existing_cells = cells[tech]
                        existing_cells.append(cell)
                        cells[tech] = existing_cells
        tigo_match_data[area] = cells
    return tigo_match_data
    

def write_dict_to_file(data, file_name):
    with open(file_name, "w") as file:
        file.write(pickle.dumps(data))


def main():
    tigo_data = open_csv("data\\Cells.csv")
    open_cell_id_data = open_csv("data\\open_cell_id.csv")
    open_cell_id_data = get_columns(open_cell_id_data, [0, 1, 2, 3, 4, 6, 7])
    tigo_data = get_columns(tigo_data, [0, 1, 2])
    tigo_data = clean_tigo_data(tigo_data)
    open_cell_id_data = clean_open_cell_id_data(open_cell_id_data)
    area_open_cell_id_dict = get_cells_in_area(open_cell_id_data)
    area_tigo_dict = match_tigo_data(tigo_data, area_open_cell_id_dict)
    

main()
