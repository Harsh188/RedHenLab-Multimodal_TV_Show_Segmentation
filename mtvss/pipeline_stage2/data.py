# Copyright (c) 2022 Harshith Mohan Kumar

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# =============================================================================

# Imports

import os
import glob

import pandas as pd
import numpy as np

from datetime import date, timedelta

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

import constants as const

class Data:
	"""
	This Data class is used to manage all of the ingestion
	and output of data related to the stage two of the pipeline.
	Various methods are provided to retrieve, manipulate and store data.
	"""

	def __init__(self,verbose:bool,file_path):
		self.verbose = verbose
		self.file_path = file_path

	def check_exist(self, file:str):
		pass

	def get_drop_indices(self, csv_file_path:str) -> np.ndarray:
		"""This method is a preprocessing filter to extract only images
			which meet a certain standard for further cluster. It useses the 
			confidence values and the duration of the clips to determine if
			the images from that section should be used or dropped.

		Args:
			csv_file_path (str): Path of the csv with metadata on image features.
		Returns:
			drop_indices (np.noarray): List of indices to drop from the npy file
		"""
		# Initialize variable to store drop indices
		drop_indices=None
		# Read csv and store as a DataFrame
		df = pd.read_csv(csv_file_path)
		# if self.verbose:
		# 	print("## Orig DF:",df)
		
		# Get indices of low confidence values
		df_filter = df['confidence'] < 0.95
		df = df.loc[df_filter]
		
		# Get indices of low and very high delta time
		df.drop(df[df['end']-df['start'] < 10].index, inplace=True)
		df.drop(df[df['end']-df['start'] > 100].index, inplace=True)
		
		# Get indices of commercials
		df.drop(df[df['label'] == 'TitleSequence'].index, inplace=True)
		
		# if self.verbose:
		# 	print("## Filtered DF:",df)
		
		# Get indices of rows to remove
		drop_indices = df.index.unique()
		
		return drop_indices

	def get_clean_arrays(self, arr, file_path:str) -> np.ndarray:
		"""This method cleans the existing features by figuring out what indices
			to drop and then mapping it to the indicies of arrays in npy file.

		Args:
			arr (np.mmap): Binary file with features to filter
			csv_file_path (str): Path of the csv with metadata on image features.
		Returns:
			final_arr (np.ndarray): Numpy array containing final features to be used
				for clustering.
		"""
		csv_file_path = file_path[:-12]+'filtered.csv'
		drop_indices = self.get_drop_indices(csv_file_path)
		
		final_drop_indices = np.empty(0)
		for x in drop_indices:
			i = x*5
			final_drop_indices = np.concatenate((final_drop_indices, [i,i+1,i+2,i+3,i+4]))
		final_drop_indices = final_drop_indices.astype(int)
		if self.verbose:
			print('\n---- Preprocessing ----\n')
			# print("## Number of features dropped:", final_drop_indices.size-final_drop_indices.size)
			print("## Indices to drop:",final_drop_indices)
		final_arr = np.delete(arr,final_drop_indices,axis=0)

		return final_arr

	def ingestion(self) -> np.ndarray:
		"""Data ingestion method to load in image features into memory using
		mmap mode. All files binary files in the /scratch directory are loaded
		and concatenated as an np.array with shape (#image_features, feature_size)
		where feature_size = 2048.
		
		Args:
			file (str): Current directory path in string format.
		Returns:
			data (List): List of image features loaded in mmap_mode.
							Contains shape (#image_features, feature_size)
		"""
		# data = np.empty((0,2048))
		data = []
		ctr = 0
		for f in glob.glob(const.SCRATCH_PATH+'tmp/'+'*image_features*.npy'):
			# data = np.append(data,np.load(f,mmap_mode='r'),axis=0)
			# Appened appropriate features
			data.append(self.get_clean_arrays(np.load(f,mmap_mode='r'),f))
			ctr+=1
			# print(data.shape)
		data_arr = np.concatenate(data,axis=0)
		print(data_arr.shape)
		mmap_path = self.file_path+'/final_data.npy'
		np.save(mmap_path,data_arr)
		data_mmap = np.load(mmap_path,mmap_mode='r')
		return data_mmap

	def get_files_between_dates(self,data,start,end):
		'''Method to get the features between a start and end date.
		Args:
			data (List): List of image features
			start (str): Date in mm/dd/yyyy format
			end (str): Date in mm/dd/yyyy format
		Returns:
			data (List): List containing concatenation image features
		'''

		start_month, start_day, start_year = start.split('/')
		end_month, end_day, end_year = end.split('/')

		start_date = date(int(start_year),int(start_month),int(start_day))
		end_date = date(int(end_year),int(end_month),int(end_day))

		delta = end_date-start_date #returns timedelta

		for i in range(delta.days+1):
			day = str(start_date+timedelta(days=i))
			file_path = const.H_GAL_HOME_PATH+'splits/tmp/'+day+'*image_features*.npy'

			for f in glob.glob(file_path):
				data.append(self.get_clean_arrays(np.load(f,mmap_mode='r'),f))


		return data

	def optimization_ingestion(self) -> np.ndarray:
		"""Data ingestion method to load in image features into memory using
		mmap mode. Unlike the regular ingestion method this one loads in a subset
		which is used to tune the number of neighbors paramter for the RNN-DBSCAN.
		
		Args:
			file (str): Current directory path in string format.
		Returns:
			data (List): List of image features loaded in mmap_mode.
							Contains shape (#image_features, feature_size)
		"""
		if self.verbose:
			print("\n --- Optimization Data Ingestion ---\n")

		# Initialize list to store array of mmaps
		data = []

		start_days = ['08/01/1996', '08/12/1996', '08/16/1996', '08/23/1996', '09/02/1996',
							'09/11/1996', '12/26/1996', '10/02/2000', '09/01/2002']
		end_days = ['08/12/1996', '08/15/1996', '08/23/1996', '09/01/1996', '09/10/1996',
							'10/17/1996', '12/27/1996', '10/06/2000', '09/06/2002']

		for i in range(len(start_days)):
			data = self.get_files_between_dates(data,start_days[i],end_days[i])
			# if self.verbose:
			# 	print("Data:",data)

		# Year and day to look for in iter 1
		# loop_1_year = '1996'
		# loop_1_day = '02'

		# ctr=0
		# for f in glob.glob(const.SCRATCH_PATH+'tmp/'+loop_1_year+'*'+loop_1_day+'*image_features*.npy'):
		# 	# data.append(np.load(f,mmap_mode='r'))
		# 	data.append(self.get_clean_arrays(np.load(f,mmap_mode='r'),f))
		# 	ctr+=1

		# # Year and day to look for in iter 2
		# loop_1_year = '2001'
		# loop_1_day = '07'

		# ctr=0
		# for f in glob.glob(const.SCRATCH_PATH+'tmp/'+loop_1_year+'*'+loop_1_day+'*image_features*.npy'):
		# 	# data.append(np.load(f,mmap_mode='r'))
		# 	data.append(self.get_clean_arrays(np.load(f,mmap_mode='r'),f))
		# 	ctr+=1

		data_arr = np.concatenate(data,axis=0)
		print(data_arr.shape)
		mmap_path = self.file_path+'/final_data.npy' 
		np.save(mmap_path,data_arr)
		np.save(const.H_GAL_HOME_PATH+'splits/final_data.npy',data_arr)

		data_mmap = np.load(mmap_path,mmap_mode='r')
		return data_mmap

		# if self.verbose:
		# 	print("## Number of files ingested:",ctr)
