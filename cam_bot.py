import io
import numpy as np
import matplotlib.pyplot as plt
def serialize_image( image ):

    return io.BufferedReader(io.BytesIO(image))

def make_heat_map( x_list, y_list):

    x = np.array(x_list)
    y = np.array(y_list)

    heatmap, xedges, yedges = np.histogram2d(x, y, bins=50)
    extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]

    plt.clf() # Clear current figure
    plt.imshow(heatmap, extent=extent)
    plt.savefig('./heat_map.png')   # save the figure to file
    plt.close()    # close the figure

def room_location( center ):

    if not center:
        return None

    x,y = center

    if 457<= x <= 584 and 90<= y <= 227:
        return "Casa circular"
    elif 100<= x <=238 and 0<= y <= 95:
        return "Hamburguesa"
    elif 9<= x <= 146 and 60<= y <= 205:
        return "Mirador del rascador"
    elif 179<= x <= 314 and 110<= y <= 178:
        return "En el bebedero"
    elif 114<= x <= 222 and 246 <= y <= 352:
        return "Balda circular del rascador"
    else:
        return "En el suelo / Unknown "

if __name__ == '__main__':
    import ip_cam
    import telegram
    import collections
    import time
    import datetime
    import configparser
    import os
    import logging

    # Read from the config file

    config_parser = configparser.ConfigParser()
    config_parser.read( os.path.dirname( os.path.realpath(__file__)) + '/conf.INI')

    ip = config_parser.get('MAIN', "IP")
    user = config_parser.get('MAIN', "User")
    password = config_parser.get('MAIN', "Password")
    bot_token = config_parser.get('MAIN','Bot_token')
    chat_id = int(config_parser.get('MAIN','Chat_id'))

    time_between_updates = int(config_parser.get('PARAMETERS', "Time_between_updates"))
    max_detection_area = int(config_parser.get('PARAMETERS', "Max_detection_area"))
    threshold = int(config_parser.get('PARAMETERS','Threshold'))

    # Prepare the log

    logger = logging.getLogger('CAM_BOT')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Prepare telegram #bot

    bot = telegram.Bot(bot_token)

    # Prepare camera

    camera = ip_cam.IPCam(ip,user=user,password=password,
                          threshold = threshold,max_detection_area=max_detection_area)

    # Prepare arrays for stats

    tracking_positions_x = []
    tracking_positions_y = []
    positions_timer = collections.Counter()

    # Main loop: Procesing frames

    logger.info('Starting main loop')


    timer = time.time
    time_in_location = 0
    last_location = None
    last_day = datetime.datetime.now().day
    timer_start = timer()
    already_notified = False
    last_notified_at = None

    for frame in camera.motion_detector_steamer(view_stream = True):

        room_position = room_location(frame.detection_center)

        logger.debug('Room position: {}'.format(room_position))

        # If we are in the same location
        if room_position is None or room_position == last_location:


            logger.debug('No detection or in same location')

            time_in_location = timer()-timer_start

            # Add coordinates to list
            if room_position is not None:
                x,y = frame.detection_center
                tracking_positions_x.append( x )
                tracking_positions_y.append( y )

            # Send image
            if last_location != last_notified_at and not already_notified and time_in_location > 10:
                logger.info('Sending image with Telegram bot')
                #Send the image
                bot.sendMessage(chat_id = chat_id, text="I have spend {} seconds in {}".format(time_in_location,last_notified_at))
                bot.sendPhoto(chat_id=chat_id, photo = serialize_image(frame.raw_image),caption=last_location)
                last_notified_at = last_location
                already_notified = True

        # If we have changed location
        else:

            logger.info('New location: {}'.format(room_position))

            # Add coordinates to list
            x,y = frame.detection_center
            tracking_positions_x.append( x )
            tracking_positions_y.append( y )

            # We are not already notified of this change

            already_notified = False

            # Add time to the time tracker and update last_location
            positions_timer[last_location] += time_in_location
            last_location = room_position

            # Reset timer
            timer_start = timer()
            time_in_location = 0


        # Send stats if 12 AM
        current_day =datetime.datetime.now().day

        logger.debug('Current day: {}'.format(current_day))

        if current_day != last_day:


            logger.debug('Making reports')

            last_day = current_day

            #Send stats
            bot.sendMessage(chat_id=chat_id, text=str(positions_timer))

            # Send heat map
            make_heat_map(tracking_positions_x,tracking_positions_y)
            with open('./heat_map.png','r') as heat_map:
                bot.sendPhoto(chat_id=chat_id,photo = heat_map)

            # Reset stats
            tracking_positions = []
            positions_timer = collections.Counter()
