#!/usr/bin/env python2
import os, sys, time, glob, gzip, shutil, urllib2
import xml.etree.ElementTree as ET

def batch_sorting_phase2(batch_urls,results_folder,upload_base,cleanup_closed=True,sort_by_project=False):
	#
	# Optional arguments: 
	# cleanup_closed: 
	#               Delete folders for 'failed' and 'in_progress' workunits for closed batches
	#               Default is False
	# sort_by_project: 
	#               Add project directory in result folder structure:
	#               TRUE: $RESULTS_FOLDER/$PROJECT/batch_XXX
	#               FALSE: $RESULTS_FOLDER/batch_XXX
	#               Default is False
	print time.strftime("%Y/%m/%d %H:%M:%S") + " Starting batch_sorting_phase2.py\n"

	# Function useful for debugging: 
	# fall back to trying to open as a local file if the url doesn't exist
	def read_url_or_file(fname):
		try:
			return urllib2.urlopen(fname,'r')
		except:
			return open(fname,'r')

	open_batches=[]
	closed_batches=[]
	batch_ul_files={}
	try:
		for dl_path in batch_urls:
			# Get lists of open and closed batches from this project
			for batch in read_url_or_file(os.path.join(dl_path,'open_batches.txt')):
				open_batches.append(batch.strip())
			for batch in read_url_or_file(os.path.join(dl_path,'closed_batches.txt')):
				closed_batches.append(batch.strip())

			# Get number of upload files for each batch
			batchxml=ET.parse(read_url_or_file(dl_path+'/batches.xml')).getroot()
			for batch in batchxml.findall('batch'):
				batchid=batch.attrib['id']
				ul_files=batch.find('ul_files').text
				batch_ul_files[batchid]=int(ul_files)
	except Exception,e:
		print e
		print 'Error downloading batch files! Aborting!'
		sys.exit(-1)

	# Set up folders if needed
	if not os.path.exists(results_folder):
		raise Exception("Error results folder doesnt exist: "+results_folder)

	# Loop over batches
	if sort_by_project:
		# Search extra level for projects
		results_path=results_folder+'/*/*'
	else:
		results_path=results_folder+'/*'
	for batch_path in glob.glob(results_path):
		# Assume batch folder is in the form results_folder/batch_XXX
		if os.path.basename(batch_path)[:6]=='batch_':
			batch=os.path.basename(batch_path).split('_')[-1]
		else:
			continue
		try:
			if batch in open_batches:
				print "Sorting batch",batch

				# Get lists of successful and failed tasks
				successful_tasks=[]
				failed_tasks=[]
				for dl_path in batch_urls:
					try:
						for task in read_url_or_file(dl_path+'/batch_'+batch+'_successful_wus'):
							successful_tasks.append(task.strip())
						for task in read_url_or_file(dl_path+'/batch_'+batch+'_failed_wus'):
							failed_tasks.append(task.strip())
					except:
						continue
				
				if len(successful_tasks)==0 and len(failed_tasks)==0:
					print "Failed to get lists of successful and failed workunits, or no completed workunits, skipping batch!"
					continue
				print len(successful_tasks),'succesfull and',len(failed_tasks),'failed tasks in batch'

				# Create folders if needed
				if len(successful_tasks)>0:
					success_folder=os.path.join(batch_path,'successful')
					if not os.path.exists(success_folder):
						os.mkdir(success_folder)
					# Set up gzipped text file for list of successful output files
					f_success= gzip.open(os.path.join(batch_path,'batch_'+batch+'.txt.gz'), 'ab')
				if len(failed_tasks)>0:
					failed_folder=os.path.join(batch_path,'failed')
					if not os.path.exists(failed_folder):
						os.mkdir(failed_folder)

				# Loop over in progress tasks
				for in_progress_task in  glob.glob(os.path.join(batch_path,'in_progress/*')):
					taskname=os.path.basename(in_progress_task)
					if taskname in successful_tasks:
						# Check if there are the right number of upload files
						ul_files=len(glob.glob(in_progress_task+'/*.zip'))
						if ul_files==batch_ul_files[batch]:
							print in_progress_task,'to',os.path.join(success_folder,taskname)
							if not os.path.exists(os.path.join(success_folder,taskname)):
								os.renames(in_progress_task,os.path.join(success_folder,taskname))
							else:
								print "Error, successful folder already exists for this task"
							# Write list of output files to f_success text file
							for zipname in glob.glob(os.path.join(success_folder,taskname,'*')):
								# Concat upload_base with second half of file path (removing results folder)
								f_success.write(upload_base+zipname[len(results_folder):]+'\n')
						else:
							print "Error, wrong number of output files for task",taskname,ul_files,batch_ul_files[batch]
					elif taskname in failed_tasks:
						print in_progress_task,'to',os.path.join(failed_folder,taskname)
						if not os.path.exists(os.path.join(failed_folder,taskname)):
							os.renames(in_progress_task,os.path.join(failed_folder,taskname))
						else:
							print "Warning, failed folder already exists for this task, merging from in_progress..."
							for fpath in glob.glob(in_progress_task+'/*'):
								fname=os.path.basename(fpath)
								failed_path=os.path.join(failed_folder,taskname,fname)
								if not os.path.exists(failed_path):
									print 'merging',fname, 'from in_progress to failed'
									os.rename(fpath,failed_path)
								else:
									print fname,'already moved to failed, deleting from in_progress'
									os.remove(fpath)
							print "deleting",in_progress_task
							os.rmdir(in_progress_task)

				# Cleanup successful tasks file
				if len(successful_tasks)>0:
					f_success.close()

			elif batch in closed_batches:
				print "batch",batch,"is closed"
				if cleanup_closed:
					fail_path=os.path.join(batch_path,'failed')
					if os.path.exists(fail_path):
						print 'Cleaning up failed workunits in:',fail_path
						shutil.rmtree(fail_path)
					in_progress_path=os.path.join(batch_path,'in_progress')
					if os.path.exists(in_progress_path):
						print 'Cleaning up in progress workunits in:',in_progress_path
						shutil.rmtree(in_progress_path)
				else:
					print "...skipping"
			else:
				print "batch",batch,"is unknown"
		except Exception,e:
			print "Error sorting batch",batch
			print e
			raise
	print time.strftime("%Y/%m/%d %H:%M:%S") + " Finished batch_sorting_phase2.py"
#####################
#
# Script Setup
# 
# Requires environment variables:
#
# BATCH_LISTS_URLS: location which the batch directories will be rsynced to
# RESULTS_FOLDER: Location of sorted results
#
# Optional environment variables: 
# UPLOAD_BASE_URL: Url for sorted files on the upload server (goes into list of successful workunits as a 'wget' file) e.g. http://upload2.cpdn.org/results
#
# Logical flags: CLEANUP_CLOSED_BATCHES, SORT_BY_PROJECT
# See notes in batch_sorting_phase2 function


batches_urls = os.environ.get('BATCH_LISTS_URLS')
results_folder = os.environ.get('RESULTS_FOLDER')

option = os.environ.get('CLEANUP_CLOSED_BATCHES')
if option is not None and option.upper() == 'TRUE':
	cleanup_closed=True
else: # Default to False
	cleanup_closed=False

option = os.environ.get('SORT_BY_PROJECT')
if option is not None and option.upper() == 'TRUE':
	sort_by_project=True
else: # Default to False
	sort_by_project=False

print 'sort by project:',sort_by_project

if not (batches_urls or results_folder):
	raise Exception("Error, environment variables required: 'BATCH_LISTS_URLS', 'RESULTS_FOLDER'")

# Split up batches_urls if using multiple projects
batches_urls=batches_urls.split(',')


# NOTE: for upload servers that are publically accessible, this should be a url e.g. 
# UPLOAD_BASE_URL = 'http://upload2.cpdn.org/results'
try:
	upload_base = os.environ['UPLOAD_BASE_URL']
except:
	print "Warning, using RESULTS_FOLDER instead of upload url."
	print "Set environment variable 'UPLOAD_BASE_URL' to specify the url files can be downloaded from"
	print "e.g. 'http://upload2.cpdn.org/results'"
	upload_base= results_folder


batch_sorting_phase2(batches_urls,results_folder,upload_base,cleanup_closed=cleanup_closed,sort_by_project=sort_by_project)
