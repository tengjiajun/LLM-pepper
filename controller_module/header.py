from controller_module.MovementController import MovementController,register,base_class
import pygame
from communication.Client import Client
from util.Config import *

register(MovementController(1280//2,360,60))