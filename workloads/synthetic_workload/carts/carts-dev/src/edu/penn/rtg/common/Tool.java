package edu.penn.rtg.common;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.util.Calendar;
import java.text.DateFormat;
import java.text.SimpleDateFormat;

public class Tool {
	public static boolean isDebug = false; 
	private static BufferedWriter outputFile;
	private static String outputFilename = "./run.log";
	private static BufferedWriter outputFile_Ak;
	private static String outputFilename_Ak = "./Ak_max.log";
	private static DateFormat dateTimeInstance = SimpleDateFormat.getDateTimeInstance();
	
	public static void debug(String str){
		if(Tool.isDebug == true){
			System.out.println(str);
		}	
	}
	
	public static void printLog(String str){
		if(Tool.isDebug == true){
			System.out.println(str);
		}
	}
	
	public static void write2log(String str){
		if(Tool.isDebug != true){
			return;
		}
		try{
			if(outputFile == null)
				outputFile = new BufferedWriter(new FileWriter(outputFilename, true));
			outputFile.write(dateTimeInstance.format(Calendar.getInstance().getTime()) + "\t" + str);
			outputFile.flush();
		}catch (IOException e){
			System.err.println("write2log error!" + e.getMessage());
			e.printStackTrace();
		}
	
	}
	

	public static void write2Aklog(String str){
		if(Tool.isDebug != true){
			return;
		}
		try{
			if(outputFile_Ak == null)
				outputFile_Ak = new BufferedWriter(new FileWriter(outputFilename_Ak, true));
			outputFile_Ak.write(dateTimeInstance.format(Calendar.getInstance().getTime()) + "\t" + str);
			outputFile_Ak.flush();
		}catch (IOException e){
			System.err.println("write2Aklog error!" + e.getMessage());
			e.printStackTrace();
		}
	
	}
	
	public static void depreciate(){
		try{
			if(outputFile != null)
				outputFile.close();
			if(outputFile_Ak != null)
				outputFile.close();
		}catch(IOException e){
			e.printStackTrace();
		}
		
	}
	
	public static void main(String args[]){
		
	    //System.out.println(dateTimeInstance.format(Calendar.getInstance().getTime()));
		
	}
}
