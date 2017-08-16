import pandas as pd
import mne
import ParsingPandas
import json
import os 
import sys
import gc
import xml.etree.ElementTree as ET

subidspellings = ["Subject", "subject", "SubjectID", "subjectid", "subjectID", "subid","subID", "SUBID", "SubID","Subject ID", "subject id", "ID"]
starttimespellings = ["starttime","startime","start time", "Start Time", "Start"]

def EDF_file_Hyp(path):
	print(path)
	EDF_file = mne.io.read_raw_edf(path,stim_channel = 'auto' , preload = True)
	#splits the fileName into list of strings seperated by \
	#[-1] takes the last string in the list which is the file name
	NameOfFile = (path.split('\\')[-1])

	jsonObj = {}
	jsonObj["epochstage"] = []
	jsonObj["epochstarttime"] = []
	
	TimeAndStage = mne.io.get_edf_events(EDF_file)
	
	StartTime = 0
	for i in range(len(TimeAndStage) - 1):
		#calculate time for start of next stage
		EndTime = TimeAndStage[i + 1][0] - TimeAndStage[i][0]
		#use given duration of current stage
		Duration = TimeAndStage[i][1]
		
		j = 0
		while j  < EndTime:
			# append NaN to json objct as epoch stage if duration of a stage  
			# ends before the start of next stage
			# ***We do this because some of the data may not correlate to eachother
			if j <= Duration:	
				jsonObj["epochstage"].append(StartTime)
			else:
				jsonObj["epochstage"].append("NaN")
			
			
			jsonObj["epochstarttime"].append(TimeAndStage[i][2])
			StartTime = StartTime + .5
			j = j + 30
	
	lastInterval = TimeAndStage[-1][0] + TimeAndStage[-1][1]		
	Time = TimeAndStage[-1][0]
	while Time < lastInterval: 
		jsonObj["epochstage"].append(StartTime)
		jsonObj["epochstarttime"].append(TimeAndStage[-1][2])
		StartTime = StartTime + .5
	
	
	#free memory
	del EDF_file
	del TimeAndStage
	
	return jsonObj

#WORKING ON IT
#XML files = scoring files need to parse it 
#def XML_File(path):
#	xml_data = open(path).read()
#	root = ET.XML(xml_data)
#	temp = []
#	for i, child in enumerate(root):
#		data = {}
#		for subchild in child:
#			stripped = subchild.tag.rstrip()
#			data[stripped] = subchild.text
#			temp.append(data)
#	xml_as_pd = pd.DataFrame(temp)
#	print (xml_as_pd)
#	k = []
#	for subdata in xml_as_pd.iterrows():
#		k.append(subdata)
#	#print (k)
#	exit()
#	return
	

def getAllFilesInTree(dirPath):
    _files = []
    for folder, subfolders, files in os.walk(dirPath):
        for _file in files:
            filePath = os.path.join(os.path.abspath(folder), _file)
            _files.append(filePath)
    return _files
	

#parsing panda objects returns jason object
def Parsing(PandaFile):
	FileKeys = PandaFile.keys()
    #cycle through keys to see if we get hits on the five keys we want and keep track of which ones we hit

	output_dict = []
	for sub_data in PandaFile.iterrows():
		output_dict.append(sub_data[1].to_json())
	return output_dict

				    	  

def StringTimetoEpoch(time):
	time = time.replace('.',':')
	temp = time.split(":")
	hours = int(temp[0])
	if temp[-1].find("AM") != -1 and temp[0].find("12"):
		hours = 0
	elif temp[-1].find("PM") != -1:
		hours = hours + 12
	#get rid of AM and PM
	temp[-1] = temp[-1].split(' ')[0]
	
	EpochTime = hours * 60 + int(temp[1]) + int(temp[2])/60
	EpochTime = round(EpochTime,1)

	return EpochTime
	
	
def EpochtoStringTime(time):
	Sec = time % 60
	time = time / 60
	Min = time % 60
	time = time / 60
	TotalTime = str(time) + ':' + str(Min) + ":" + str(Sec)
	
	
#demographics file contains te data you would need fro the other one
#in the name of the demographics file it tells you which file to access for its data type
#from file path and name of scoring we know the SubjectID 
#each file data base needs different parsing method
#we will neee a  checker to see which parse method is needed
#all demographics files contain same information

 
#returns an integer determiing which parse method to use
#if found == 0 file contain only s and 0s
#if found == 1 file contain latency and type(sleep stage mode)
#if found == 2 file contain sleep stage , and time 
KeyWords = ["latency","RemLogic"]
def ScoringParseChoose(file):
	found = 0 
	firstline = file.readline()
	file.seek(0)
	for count in range(len(KeyWords)):
		if firstline.find(KeyWords[count]) != -1:
			found = count + 1
	return found
	
# Type 0		
def BasicScoreFile(file):
	JasonObj = {}
	JasonObj["epochstage"] = []
	JasonObj["Type"] = "0"
	for line in file:
		temp = line.split(' ')
		temp = temp[0].split('\t')
		temp[0] = temp[0].strip('\n')
		JasonObj["epochstage"].append(temp[0])
	return JasonObj	

# Type 1		Example: SpencerLab
#these files give time in seconds in 30 sec interval
#start of sleep time is given in demographic file
def LatTypeScoreFile(file):
	JasonObj = {}
	JasonObj["Type"] = "1"
	JasonObj["epochstage"] = []
	JasonObj["epochstarttime"] = []
	file.readline()						#done so that we can ignore the first line which just contain variable names
	for line in file:
		temp = line.rstrip()
		temp = line.split('  ')
		if len(temp) == 1:
			temp = line.split('\t')		
		temp[-1] = temp[-1].strip('\n')
		JasonObj["epochstage"].append(temp[-1])
		time = temp[0]
		time = int(time) / 60 
		JasonObj["epochstarttime"].append(time)		
	return JasonObj	


# Type 2
def FullScoreFile(file):
	JasonObj = {}
	JasonObj["Type"] = "2"
	JasonObj["epochstage"] = []
	JasonObj["epochstarttime"] = []
#find line with SleepStage
#find position of SleepStage and Time
	StartSplit = False
	
	SleepStagePos = 0
	TimePos = 0
	EventPos = 0
	
	for line in file:
		if StartSplit and line.strip() != '':
			temp = line.split('\t')
			
			if len(temp) > EventPos and temp[EventPos].find("MCAP") == -1:
				JasonObj["epochstage"].append(temp[SleepStagePos])
				time = StringTimetoEpoch(temp[TimePos])
				JasonObj["epochstarttime"].append(time)
			
		if line.find("Sleep Stage") != -1:
			StartSplit = True
			temp = line.split('\t')
			for i in range(len(temp)):
				if temp[i] == "Sleep Stage":
					SleepStagePos = i
				if temp[i].find("Time") != -1:
					TimePos = i
				if temp[i].find("Event") != -1:
					EventPos = i
	return JasonObj
	
	

def GetSubIDandStudyID(filePath, CurrentDict):
	holder = filePath.split('.')
	holder = holder[0].split('\\')
	if not "subjectid" in CurrentDict.keys():
		VisitAndSubID = holder[-1].split('_')
		if VisitAndSubID[0] != VisitAndSubID[-1]:
			CurrentDict["visitid"] = VisitAndSubID[1][5:]
		else:
			CurrentDict["visitid"] = 1
						
		CurrentDict["subjectid"] = VisitAndSubID[0][5:]
	CurrentDict["studyid"] = holder[-3]
	if isinstance(CurrentDict["subjectid"],str):
		CurrentDict["subjectid"].strip(' ')
		CurrentDict["subjectid"] = CurrentDict["subjectid"].lower()
	return CurrentDict
	

#gets the file reads it using appropriate read method then calls appropriate parse function 
#does fine tuning for jason obj to uniform include subjectID and studyid	
def MakeJsonObj(file):
	#demographic Files
	if file.endswith("xls") or file.endswith("xlsx") or file.endswith(".csv"):
		#do the parsing
		JsonList = ParsingPandas.main(file)
		for i in range(len(JsonList)):
			JsonList[i] = json.loads(JsonList[i])
		#add studyid from name of file
		temp = file.split('.')
		temp = temp[0].split('\\')
		temp = temp[-1].split('ics_')
		temp = temp[-1]
		
		returningList = []
		for i in range(len(JsonList)):
			if "subjectid" not in JsonList[i]:
				#checks for all the common different spellings of subjectid and casts it to subjectid in dict
				for spell in subidspellings:
					if spell in JsonList[i]:
						JsonList[i]["subjectid"] = JsonList[i][spell]
				#subjectid becomes N/A if comon spelling for subjectid not found
				if "subjectid" not in JsonList[i]:
					JsonList[i]["subjectid"] = 'N/A'
				
				#if subject id is a word makes it into all lowercase
				if isinstance(JsonList[i]["subjectid"],str):
					JsonList[i]["subjectid"] = JsonList[i]["subjectid"].lower()
		
			JsonList[i]["studyid"] = temp
			#JsonList[i]["visitid"] = visit
		
		return JsonList

	#these are the scoring files (txt)
	elif file.endswith(".txt"):
		JSON = {}
		temp = open(file, 'r')
		ScoreFileType = ScoringParseChoose(temp)
		if ScoreFileType == 0:
			JSON = BasicScoreFile(temp)
		elif ScoreFileType == 1:
			JSON = LatTypeScoreFile(temp)
		elif ScoreFileType == 2:
			JSON = FullScoreFile(temp)
		else:
			print("other")

		#add studyid and subectID to JSON for scoring
		JSON = GetSubIDandStudyID(file,JSON)
		return JSON
	
	#EDF+ files which contain scoring data
	elif file.endswith(".edf"):
		JSON = {}
		JSON = EDF_file_Hyp(file)

		#add studyid and subectID to JSON for scoring
		JSON = GetSubIDandStudyID(file,JSON)		
		return JSON	
	
#	elif file.endswith('.xml'):
#		JSON = {}
#		JSON = XML_File(file)
#
#		#add studyid and subectID to JSON for scoring
#		JSON = GetSubIDandStudyID(file,JSON)		
#		return JSON		
	
	
	return 1

#Demo is a list of dictionary from demographic files
#Score is  list of dictionar from all score files
def CombineJson(Demo, Score):
	ReturnJsonList = []
	#this for loop goes through all the demographics data
	for i in range(len(Demo)):
		Found = False
		#this for loop goes through all the scoring datas
		for j in range(len(Score)):
			#check if the studyid and subjectid of the data is the same
			if Demo[i]["studyid"] == Score[j]["studyid"] and str(Demo[i]["subjectid"]) == str(Score[j]["subjectid"]):
				temp = {**Demo[i],**Score[j]}
					
				#type 0 files have epoch timestamps we add it now
				if temp["Type"] == '0':
					temp["epochstarttime"] = []
					for spell in starttimespellings:
						if spell in temp.keys():
							temp["epochstarttime"].append(StringTimetoEpoch(temp[spell]))

					for samples in range(len(temp["epochstage"]) - 1):
						epochTime = temp["epochstarttime"][samples] + .5
						if epochTime >= 1440:
							epochTime = 0
						temp["epochstarttime"].append(epochTime)
					
				#type 1 files need to add the time sleeping to start time from demographics file data
				elif temp["Type"] == '1':
					StartTime = 0
						
					for spell in starttimespellings:
						if spell in temp.keys():
							StartTime = StringTimetoEpoch(temp[spell])
								
					for index in range(len(temp["epochstarttime"])):
						CheckOver = temp["epochstarttime"][index] + StartTime
						if CheckOver >= 1440:
							CheckOver = CheckOver - 1440
						temp["epochstarttime"][index] = CheckOver
					
				ReturnJsonList.append(temp)
				Found = True
				
				
		if Found == False:
			print("no match found for: " + str(Demo[i]["studyid"]) + ", " + str(Demo[i]["subjectid"]))

			
	return ReturnJsonList
		
#Parameter JsonList created from one demographics file of a particular study
#          JsonList created from all score files for the same study
#		   file  is the absolute path where new directory jsonObjects will be created which contain the data from score+demographic
def CreateJsonFile(JsonObjListDemo, JsonObjList, file):
		#call function to combine the lists into one json obj
	FinishedJson = CombineJson(JsonObjListDemo, JsonObjList)
	
	#save each object(patient) as own file 
	#create a folder in original file path
	#save all objects in folder as file
	directory = file + "/jsonObjects"
	if not os.path.exists(directory):
		os.mkdir(directory)
	for Object in FinishedJson:
		#study_subid_visit_session     <-- session not added yet
		if "session" in Object.keys():
			filename =  directory + '/' + str(Object["studyid"]) +  "_subjectid" + str(Object["subjectid"]) + "_visit" + str(Object["visitid"]) + "_session" +str(Object["session"]) + ".json"
		else:
			filename =  directory + '/' + str(Object["studyid"]) +  "_subjectid" + str(Object["subjectid"]) + "_visit" + str(Object["visitid"])+ ".json"
		jsonfile = open(filename,'w')
		json.dump(Object,jsonfile)
	return


#Main
#main chooses which parsing function is called
#Three methods of using the function
#1) input the file path into main when called 
#2) input the file path as the first index of the cmd line argument 
#3) call main with no parameters and cmd line argument and manulally input when prompted
def main(file = None):
	if file == None:
		if len(sys.argv) > 1:
			file = sys.argv[1]
		else:
			file = input("Enter absolute path to the head Directory containing the scorings folders: ")
    
	#filesInTemp = getAllFilesInTree(testdir)
	filelist = getAllFilesInTree(file)
	
	#now we have a list of Json Objs made from all files in folder
	#fist will contain all json obj from the score files
	#second will contain all json objs from demographic files
	JsonObjList = []
	JsonObjListDemo = []
	
	for files in filelist:
		temp = {}
		temp = GetSubIDandStudyID(files,temp)
		# Need to set studyid of current study
		#if study id changes it means we are in different study folder
		#so we can connect the Json objects and create the json files
		if ".xlsx" in files and files != filelist[0]:
			CreateJsonFile(JsonObjListDemo, JsonObjList, file)	
			CurentStudy = temp['studyid']
			JsonObjListDemo = []
			JsonObjList = []
			gc.collect()
			HitOnce = False
				
		if ('scorefiles' in files) or not (('.txt' in files) or ('.edf' in files) or ('jsonObjects' in files) ):
			JsonObj = MakeJsonObj(files)
			if isinstance(JsonObj, int):
				print(files + " is not comprehendable")
			elif isinstance(JsonObj,dict):
				JsonObjList.append(JsonObj)
			elif isinstance(JsonObj,list):
				for i in JsonObj:
					JsonObjListDemo.append(i)
		

	CreateJsonFile(JsonObjListDemo, JsonObjList, file)		
		
main() #'C:/source/mednickdb/temp/AllData/CCSHS')#AllData/ExampleMASSData')

